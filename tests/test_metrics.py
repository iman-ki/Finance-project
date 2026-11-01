"""Every metric checked against numbers worked out by hand.

Returns used: +10%, -5%, +2%, -10%.
Wealth path: 1.10, 1.045, 1.0659, 0.95931.
Mean = -0.0075. Deviations: 0.1075, -0.0425, 0.0275, -0.0925.
Sum of squared deviations = 0.022675, sample variance = 0.022675 / 3.
"""

import pandas as pd
import pytest

from qrp.evals import metrics

R = pd.Series([0.10, -0.05, 0.02, -0.10])
VARIANCE = 0.022675 / 3


def test_total_return():
    assert metrics.total_return(R) == pytest.approx(0.95931 - 1)


def test_cagr_two_years():
    # 4 periods at 2 per year = 2 years, so CAGR = 0.95931^(1/2) - 1.
    assert metrics.cagr(R, periods_per_year=2) == pytest.approx(0.95931**0.5 - 1)


def test_volatility_annualized():
    assert metrics.volatility(R, periods_per_year=52) == pytest.approx((VARIANCE * 52) ** 0.5)


def test_sharpe_zero_risk_free():
    expected = -0.0075 / VARIANCE**0.5 * 52**0.5
    assert metrics.sharpe_ratio(R, periods_per_year=52) == pytest.approx(expected)


def test_sharpe_subtracts_risk_free_per_period():
    # 52% a year over 52 periods = 1% per period, so the mean excess return is -1.75%.
    # Subtracting a constant does not change the standard deviation.
    expected = -0.0175 / VARIANCE**0.5 * 52**0.5
    assert metrics.sharpe_ratio(R, 52, risk_free_rate=0.52) == pytest.approx(expected)


def test_drawdown_path():
    # Peak is 1.10 after the first period: 1.045/1.1 - 1, 1.0659/1.1 - 1, 0.95931/1.1 - 1.
    assert metrics.drawdown(R).tolist() == pytest.approx([0.0, -0.05, -0.031, -0.1279])
    assert metrics.max_drawdown(R) == pytest.approx(-0.1279)


def test_drawdown_counts_starting_value_as_peak():
    # Losing 10% right away is a 10% drawdown, even though no higher value was recorded.
    dd = metrics.drawdown(pd.Series([-0.10, 0.05]))
    assert dd.tolist() == pytest.approx([-0.10, 0.9 * 1.05 - 1])


def test_value_at_risk_and_cvar():
    # Sorted: -0.10, -0.05, 0.02, 0.10. The 25% quantile sits 3/4 of the way from the
    # 1st to the 2nd value: -0.10 + 0.75 * 0.05 = -0.0625, so VaR(75%) = 6.25%.
    # Only -0.10 is at or beyond it, so CVaR = 10%.
    assert metrics.value_at_risk(R, confidence=0.75) == pytest.approx(0.0625)
    assert metrics.conditional_value_at_risk(R, confidence=0.75) == pytest.approx(0.10)


def test_summary_has_every_metric():
    keys = set(metrics.summary(R, periods_per_year=52))
    assert keys == {"total_return", "cagr", "volatility", "sharpe", "max_drawdown", "var", "cvar"}
