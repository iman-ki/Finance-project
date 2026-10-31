import numpy as np
import pandas as pd
import pytest

from qrp.backtest import run
from qrp.backtest.engine import rebalance_dates

JAN = pd.to_datetime(["2024-01-05", "2024-01-12", "2024-01-19"])


def frame(data, index=JAN):
    return pd.DataFrame(data, index=index, dtype=float)


def test_weights_earn_the_next_period_return():
    # A: 100 -> 110 (+10%) -> 99 (-10%). Fully invested from the first date.
    prices = frame({"A": [100, 110, 99]})
    result = run(prices, frame({"A": [1, 1, 1]}), 0, 0, rebalance="every_period")
    assert result.returns.tolist() == pytest.approx([0.10, -0.10])


def test_no_look_ahead():
    # Deciding to buy on the second date must not capture the +10% that led up to it.
    prices = frame({"A": [100, 110, 99]})
    result = run(prices, frame({"A": [0, 1, 1]}), 0, 0, rebalance="every_period")
    assert result.returns.tolist() == pytest.approx([0.0, -0.10])


def test_costs_charged_on_turnover():
    # Buying 100% costs 10 bp up front: (1 - 0.001) * 1.10 - 1 = 0.0989. No trade after.
    prices = frame({"A": [100, 110, 99]})
    result = run(
        prices, frame({"A": [1, 1, 1]}), commission_bps=7, slippage_bps=3, rebalance="every_period"
    )
    assert result.turnover.tolist() == pytest.approx([1.0, 0.0])
    assert result.costs.tolist() == pytest.approx([0.001, 0.0])
    assert result.returns.tolist() == pytest.approx([0.0989, -0.10])


def test_holdings_drift_between_rebalances():
    # 50/50 at the start, no rebalance until month end.
    # Period 1: A doubles, B flat. Portfolio +50%; weights drift to 2/3 A, 1/3 B.
    # Period 2: A halves. Portfolio return = 2/3 * -50% = -1/3. Wealth back to 1.0,
    # which matches holding the shares: 0.5 in A -> 1.0 -> 0.5, plus 0.5 in B.
    prices = frame({"A": [100, 200, 100], "B": [100, 100, 100]})
    targets = frame({"A": [0.5] * 3, "B": [0.5] * 3})
    result = run(prices, targets, 0, 0, rebalance="monthly")
    assert result.returns.tolist() == pytest.approx([0.5, -1 / 3])
    assert result.weights.iloc[2].tolist() == pytest.approx([2 / 3, 1 / 3])


def test_partial_investment_keeps_cash_flat():
    prices = frame({"A": [100, 120, 120]})
    result = run(prices, frame({"A": [0.5, 0.5, 0.5]}), 0, 0, rebalance="every_period")
    assert result.returns.iloc[0] == pytest.approx(0.10)


def test_equity_starts_at_initial_capital():
    prices = frame({"A": [100, 110, 99]})
    result = run(prices, frame({"A": [1, 1, 1]}), 0, 0, rebalance="every_period")
    assert result.equity(10_000).tolist() == pytest.approx([10_000, 11_000, 9_900])


def test_monthly_rebalance_dates_are_month_ends_plus_start():
    fridays = pd.to_datetime(
        ["2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26", "2024-02-02", "2024-02-09"]
    )
    mask = rebalance_dates(fridays, "monthly")
    assert mask.tolist() == [True, False, False, True, False, True]


def test_missing_price_for_held_asset_is_an_error():
    prices = frame({"A": [100, np.nan, 99]})
    with pytest.raises(ValueError, match="missing price"):
        run(prices, frame({"A": [1, 1, 1]}), 0, 0, rebalance="every_period")


def test_unknown_rebalance_rule():
    with pytest.raises(ValueError, match="unknown rebalance rule"):
        rebalance_dates(JAN, "hourly")
