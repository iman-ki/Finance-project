"""Provider tests run offline: they use saved files and fake Yahoo tables, never the network."""

import os
import time

import pandas as pd
import pytest

from qrp.data.providers.yfinance import YFinanceError, YFinanceProvider, clean_history

DATES = pd.date_range("2024-01-02", periods=3, freq="B", tz="America/New_York")


def history(closes):
    return pd.DataFrame({"Open": closes, "Close": closes}, index=DATES)


def save(raw_dir, ticker, closes, age_hours=0.0):
    path = raw_dir / "yfinance" / f"{ticker}_daily.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"adj_close": closes}, index=DATES.tz_localize(None)).to_parquet(path)
    then = time.time() - age_hours * 3600
    os.utime(path, (then, then))


def test_clean_history_strips_timezone_and_keeps_close():
    series = clean_history(history([100.0, 101.0, 102.0]), "SPY")
    assert series.tolist() == [100.0, 101.0, 102.0]
    assert series.index.tz is None
    assert series.name == "SPY"


def test_clean_history_drops_missing_and_duplicate_dates():
    table = history([100.0, None, 102.0])
    series = clean_history(table, "SPY")
    assert series.tolist() == [100.0, 102.0]


def test_empty_download_is_a_clear_error():
    with pytest.raises(YFinanceError, match="no data returned for 'XYZ'"):
        clean_history(pd.DataFrame(), "XYZ")


def test_fresh_saved_copy_is_used_without_network(tmp_path, monkeypatch):
    save(tmp_path, "SPY", [100.0, 101.0, 102.0])
    provider = YFinanceProvider(raw_path=tmp_path)
    monkeypatch.setattr(provider, "_fetch", lambda t: pytest.fail("should not download"))
    prices = provider.get_prices(["SPY"], start="2024-01-03")
    assert prices["SPY"].tolist() == [101.0, 102.0]


def test_refresh_downloads_and_saves(tmp_path, monkeypatch):
    save(tmp_path, "SPY", [1.0, 2.0, 3.0])
    provider = YFinanceProvider(raw_path=tmp_path, refresh=True)
    monkeypatch.setattr(provider, "_fetch", lambda t: clean_history(history([7.0, 8.0, 9.0]), t))
    assert provider.get_prices(["SPY"], start="2024-01-01")["SPY"].tolist() == [7.0, 8.0, 9.0]
    again = YFinanceProvider(raw_path=tmp_path)  # now served from the saved file
    assert again.get_prices(["SPY"], start="2024-01-01")["SPY"].tolist() == [7.0, 8.0, 9.0]


def test_stale_copy_is_used_when_download_fails(tmp_path, monkeypatch):
    save(tmp_path, "SPY", [100.0, 101.0, 102.0], age_hours=48)
    provider = YFinanceProvider(raw_path=tmp_path, cache_max_age_hours=24)

    def fail(ticker):
        raise YFinanceError("rate limited")

    monkeypatch.setattr(provider, "_fetch", fail)
    with pytest.warns(UserWarning, match="rate limited"):
        prices = provider.get_prices(["SPY"], start="2024-01-01")
    assert len(prices) == 3


def test_failed_download_without_saved_copy_raises(tmp_path, monkeypatch):
    provider = YFinanceProvider(raw_path=tmp_path)

    def fail(ticker):
        raise YFinanceError("no network")

    monkeypatch.setattr(provider, "_fetch", fail)
    with pytest.raises(YFinanceError, match="no network"):
        provider.get_prices(["SPY"], start="2024-01-01")


def test_unsupported_frequency():
    with pytest.raises(ValueError, match="not supported"):
        YFinanceProvider(frequency="hourly")
