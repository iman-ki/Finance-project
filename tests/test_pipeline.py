"""End-to-end run on saved data: config in, report folder out."""

import json

import numpy as np
import pandas as pd
import pytest

from qrp import pipeline
from qrp.core.config import load_config
from qrp.strategies.buy_and_hold import BuyAndHold


def test_buy_and_hold_weights():
    prices = pd.DataFrame({"SPY": [np.nan, 100, 101], "TLT": [50, 51, 52]})
    weights = BuyAndHold("SPY").target_weights(prices)
    assert weights["SPY"].tolist() == [0.0, 1.0, 1.0]
    assert weights["TLT"].tolist() == [0.0, 0.0, 0.0]


def test_full_run_writes_report(tmp_path):
    dates = pd.date_range("2020-01-03", periods=120, freq="W-FRI")
    closes = 100 * np.cumprod(1 + np.random.default_rng(0).normal(0.002, 0.02, len(dates)))
    raw = {
        "Weekly Adjusted Time Series": {
            d.strftime("%Y-%m-%d"): {"5. adjusted close": str(c)} for d, c in zip(dates, closes)
        }
    }
    raw_file = tmp_path / "raw" / "alphavantage" / "SPY_weekly.json"
    raw_file.parent.mkdir(parents=True)
    raw_file.write_text(json.dumps(raw))

    config = load_config()
    config["data"]["raw_path"] = str(tmp_path / "raw")
    config["data"]["cache_max_age_hours"] = 1e9
    config["reporting"]["output_path"] = str(tmp_path / "reports")

    report = pipeline.run(config)

    out = report.parent
    for name in ["report.md", "equity.png", "drawdown.png", "metrics.csv", "returns.csv"]:
        assert (out / name).exists()
    metrics = pd.read_csv(out / "metrics.csv", index_col=0)
    # Strategy is buy-and-hold SPY, the same as the benchmark, so it is reported once.
    assert list(metrics.columns) == ["buy_and_hold(SPY)"]
    # One entry trade of 100% at 3 bp, then nothing.
    assert metrics.loc["total_costs"].iloc[0] == pytest.approx(0.0003)
    expected_growth = (1 - 0.0003) * closes[-1] / closes[0]
    assert metrics.loc["final_value"].iloc[0] == pytest.approx(10_000 * expected_growth)
