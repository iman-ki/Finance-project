"""Provider tests run offline: they use saved responses, never the real API."""

import json
import os
import time

import pytest

from qrp.data.providers.alphavantage import (
    AlphaVantageError,
    AlphaVantageProvider,
    parse_adjusted_close,
)


def payload(closes: dict[str, float]) -> dict:
    return {
        "Meta Data": {},
        "Weekly Adjusted Time Series": {
            date: {"4. close": str(c + 1), "5. adjusted close": str(c)}
            for date, c in closes.items()
        },
    }


SAMPLE = payload({"2024-01-19": 102.0, "2024-01-05": 100.0, "2024-01-12": 101.0})


def save(raw_dir, ticker, data, age_hours=0.0):
    path = raw_dir / "alphavantage" / f"{ticker}_weekly.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    then = time.time() - age_hours * 3600
    os.utime(path, (then, then))


def test_parse_uses_adjusted_close_oldest_first():
    series = parse_adjusted_close(SAMPLE)
    assert series.tolist() == [100.0, 101.0, 102.0]
    assert series.index.is_monotonic_increasing


def test_parse_error_response():
    with pytest.raises(AlphaVantageError, match="premium"):
        parse_adjusted_close({"Information": "This is a premium endpoint."})


def test_fresh_saved_copy_is_used_without_network(tmp_path, monkeypatch):
    save(tmp_path, "SPY", SAMPLE)
    provider = AlphaVantageProvider(raw_path=tmp_path)
    monkeypatch.setattr(provider, "_fetch", lambda t: pytest.fail("should not download"))
    prices = provider.get_prices(["SPY"], start="2024-01-10")
    assert prices["SPY"].tolist() == [101.0, 102.0]


def test_stale_copy_is_used_when_download_fails(tmp_path, monkeypatch):
    save(tmp_path, "SPY", SAMPLE, age_hours=48)
    provider = AlphaVantageProvider(raw_path=tmp_path, cache_max_age_hours=24)

    def fail(ticker):
        raise AlphaVantageError("quota reached")

    monkeypatch.setattr(provider, "_fetch", fail)
    with pytest.warns(UserWarning, match="quota reached"):
        prices = provider.get_prices(["SPY"], start="2024-01-01")
    assert len(prices) == 3


def test_missing_key_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    with pytest.raises(AlphaVantageError, match="ALPHAVANTAGE_API_KEY"):
        AlphaVantageProvider(raw_path=tmp_path).get_prices(["SPY"], start="2024-01-01")


def test_daily_is_rejected_with_reason():
    with pytest.raises(ValueError, match="premium"):
        AlphaVantageProvider(frequency="daily")
