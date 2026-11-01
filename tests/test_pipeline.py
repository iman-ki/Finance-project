"""End-to-end run on saved data: config in, report folder out."""

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


DATES = pd.bdate_range("2020-01-02", periods=300)
CLOSES = 100 * np.cumprod(1 + np.random.default_rng(0).normal(0.0005, 0.01, len(DATES)))


def offline_config(tmp_path):
    raw_file = tmp_path / "raw" / "yfinance" / "SPY_daily.parquet"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"adj_close": CLOSES}, index=DATES).to_parquet(raw_file)
    config = load_config()
    config["data"]["provider"] = "yfinance"
    config["data"]["frequency"] = "daily"
    config["data"]["raw_path"] = str(tmp_path / "raw")
    config["data"]["cache_max_age_hours"] = 1e9
    config["evals"]["output_path"] = str(tmp_path / "reports")
    return config


def test_full_run_writes_report(tmp_path):
    closes = CLOSES
    report = pipeline.run(offline_config(tmp_path))

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
    assert "one-day horizon" in (out / "report.md").read_text(encoding="utf-8")


def test_risk_management_sits_between_strategy_and_simulation(tmp_path):
    # Strategy asks for 100% SPY; a 50% cap leaves half in cash. With no costs and a reset to
    # 50/50 every period, each return is exactly half of SPY's. (With monthly rebalancing the
    # SPY share would drift away from 50% between resets, as a real portfolio does.)
    config = offline_config(tmp_path)
    config["risk_management"]["params"]["max_weight"] = 0.5
    config["backtest"].update(commission_bps=0, slippage_bps=0, rebalance="every_period")
    sim = pipeline.simulate(config)

    strategy = sim.runs["buy_and_hold(SPY)"]
    spy_returns = pd.Series(CLOSES, index=DATES).pct_change().dropna()
    assert strategy.returns.to_numpy() == pytest.approx(0.5 * spy_returns.to_numpy())
    assert sim.target_weights["SPY"].iloc[-1] == 1.0
    assert sim.allowed_weights["SPY"].iloc[-1] == 0.5
    assert sim.risk_adjusted_dates() == len(DATES)
    assert "Benchmark: SPY" in sim.runs  # the benchmark is not capped, so both lines show
