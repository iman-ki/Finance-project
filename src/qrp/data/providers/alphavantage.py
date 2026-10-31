"""Alpha Vantage price provider.

Free-key limits (checked 2026-10-31): 25 requests per day, 1 request per second.
Daily history is premium: the free key returns only the last 100 days, unadjusted.
So this provider uses the weekly and monthly *adjusted* series, which are free, start
in late 1999 and fold dividends and splits into the adjusted close.

Each raw API response is saved untouched under data/raw/alphavantage/. Later runs read
that file instead of spending requests, and any result can be re-derived offline.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import warnings
from pathlib import Path

import pandas as pd

from qrp.core.config import PROJECT_ROOT
from qrp.data.base import DataProvider, providers

API_URL = "https://www.alphavantage.co/query"
API_KEY_VAR = "ALPHAVANTAGE_API_KEY"
FUNCTIONS = {
    "weekly": "TIME_SERIES_WEEKLY_ADJUSTED",
    "monthly": "TIME_SERIES_MONTHLY_ADJUSTED",
}
MIN_SECONDS_BETWEEN_REQUESTS = 1.2


class AlphaVantageError(RuntimeError):
    """The API answered, but without data (bad key, quota, premium-only, unknown ticker)."""


def parse_adjusted_close(payload: dict) -> pd.Series:
    """Extract the adjusted close series from a raw API response, oldest first."""
    key = next((k for k in payload if "Time Series" in k), None)
    if key is None:
        message = payload.get("Error Message") or payload.get("Information") or payload.get("Note")
        raise AlphaVantageError(message or f"unexpected response keys: {list(payload)}")
    rows = payload[key]
    series = pd.Series(
        {pd.Timestamp(date): float(bar["5. adjusted close"]) for date, bar in rows.items()}
    ).sort_index()
    series.index.name = "date"
    return series


@providers.register("alphavantage")
class AlphaVantageProvider(DataProvider):
    def __init__(
        self,
        frequency: str = "weekly",
        raw_path: Path | str = PROJECT_ROOT / "data" / "raw",
        cache_max_age_hours: float = 24,
        refresh: bool = False,
    ) -> None:
        if frequency not in FUNCTIONS:
            raise ValueError(
                f"frequency '{frequency}' not supported. Use one of {sorted(FUNCTIONS)}; "
                "daily history needs a premium Alpha Vantage key."
            )
        self.frequency = frequency
        self.raw_dir = Path(raw_path) / "alphavantage"
        self.max_age_seconds = cache_max_age_hours * 3600
        self.refresh = refresh
        self._last_request = 0.0

    def get_prices(self, tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
        prices = pd.DataFrame({t: parse_adjusted_close(self._load(t)) for t in tickers})
        return prices.sort_index().loc[start:end]

    def _raw_file(self, ticker: str) -> Path:
        return self.raw_dir / f"{ticker}_{self.frequency}.json"

    def _load(self, ticker: str) -> dict:
        path = self._raw_file(ticker)
        if path.exists() and not self.refresh:
            age = time.time() - path.stat().st_mtime
            if age < self.max_age_seconds:
                return json.loads(path.read_text(encoding="utf-8"))
        try:
            payload = self._fetch(ticker)
        except (AlphaVantageError, OSError) as exc:
            if not path.exists():
                raise
            warnings.warn(f"{ticker}: download failed ({exc}); using saved copy from {path}")
            return json.loads(path.read_text(encoding="utf-8"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _fetch(self, ticker: str) -> dict:
        api_key = os.environ.get(API_KEY_VAR)
        if not api_key:
            raise AlphaVantageError(f"{API_KEY_VAR} is not set (put it in .env)")
        wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        query = urllib.parse.urlencode(
            {"function": FUNCTIONS[self.frequency], "symbol": ticker, "apikey": api_key}
        )
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as response:
            payload = json.load(response)
        self._last_request = time.monotonic()
        parse_adjusted_close(payload)  # raise before saving an error response as data
        return payload
