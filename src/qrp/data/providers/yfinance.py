"""Yahoo Finance price provider (via the yfinance package). Free, no key, daily history.

Prototyping source only: unofficial, can break without notice, has survivorship bias and
occasional adjustment quirks. Swap it for a better provider by changing `data.provider`
in the config; nothing else depends on it.

Prices are split- and dividend-adjusted closes (`auto_adjust=True`). Each download is
saved under data/raw/yfinance/ and reused until it is `cache_max_age_hours` old, so
reruns need no network and a result can be re-derived offline.
"""

from __future__ import annotations

import time
import warnings
from pathlib import Path

import pandas as pd

from qrp.core.config import PROJECT_ROOT
from qrp.data.base import DataProvider, providers

INTERVALS = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}
# Earliest date requested. Each ticker simply starts when Yahoo's history does.
FULL_HISTORY_START = "1980-01-01"


class YFinanceError(RuntimeError):
    """Yahoo answered without usable data (unknown ticker, no network, rate limit)."""


@providers.register("yfinance")
class YFinanceProvider(DataProvider):
    def __init__(
        self,
        frequency: str = "daily",
        raw_path: Path | str = PROJECT_ROOT / "data" / "raw",
        cache_max_age_hours: float = 24,
        refresh: bool = False,
    ) -> None:
        if frequency not in INTERVALS:
            raise ValueError(
                f"frequency '{frequency}' not supported. Use one of {sorted(INTERVALS)}"
            )
        self.frequency = frequency
        self.raw_dir = Path(raw_path) / "yfinance"
        self.max_age_seconds = cache_max_age_hours * 3600
        self.refresh = refresh

    def get_prices(self, tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
        prices = pd.DataFrame({t: self._load(t) for t in tickers})
        return prices.sort_index().loc[start:end]

    def _raw_file(self, ticker: str) -> Path:
        return self.raw_dir / f"{ticker}_{self.frequency}.parquet"

    def _load(self, ticker: str) -> pd.Series:
        path = self._raw_file(ticker)
        if path.exists() and not self.refresh and self._is_fresh(path):
            return _read(path)
        try:
            series = self._fetch(ticker)
        except YFinanceError as exc:
            if not path.exists():
                raise
            warnings.warn(f"{ticker}: download failed ({exc}); using saved copy from {path}")
            return _read(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        series.to_frame("adj_close").to_parquet(path)
        return series

    def _is_fresh(self, path: Path) -> bool:
        return time.time() - path.stat().st_mtime < self.max_age_seconds

    def _fetch(self, ticker: str) -> pd.Series:
        import yfinance as yf  # imported here so the other providers work without it

        # One ticker at a time: yfinance's parallel mode can fail with 'database is locked'.
        yf.set_tz_cache_location(str(PROJECT_ROOT / "data" / "cache" / "yfinance_tz"))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # yfinance trips pandas deprecation warnings
                history = yf.Ticker(ticker).history(
                    start=FULL_HISTORY_START,
                    interval=INTERVALS[self.frequency],
                    auto_adjust=True,
                    actions=False,
                )
        except Exception as exc:  # yfinance raises many unrelated types
            raise YFinanceError(f"{type(exc).__name__}: {exc}") from exc
        return clean_history(history, ticker)


def clean_history(history: pd.DataFrame, ticker: str) -> pd.Series:
    """Turn yfinance's table into one adjusted-close series with plain (timezone-free) dates."""
    if history is None or history.empty or "Close" not in history:
        raise YFinanceError(f"no data returned for '{ticker}' (wrong symbol or Yahoo is down)")
    series = history["Close"].dropna().astype(float)
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    series.index.name = "date"
    series.name = ticker
    return series


def _read(path: Path) -> pd.Series:
    series = pd.read_parquet(path)["adj_close"]
    series.name = path.stem.rsplit("_", 1)[0]
    return series
