"""Performance and risk metrics. Each takes a series of per-period simple returns.

`periods_per_year` converts per-period numbers to yearly ones: 52 for weekly data,
12 for monthly, 252 for daily (see qrp.core.config.PERIODS_PER_YEAR).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def total_return(returns: pd.Series) -> float:
    """Growth of 1 over the whole period, minus 1. Compounds: (1+r1)(1+r2)... - 1."""
    return float((1 + returns).prod() - 1)


def cagr(returns: pd.Series, periods_per_year: int) -> float:
    """Compound annual growth rate: the constant yearly return giving the same end value."""
    years = len(returns) / periods_per_year
    return float((1 + total_return(returns)) ** (1 / years) - 1)


def volatility(returns: pd.Series, periods_per_year: int) -> float:
    """Annualized standard deviation of returns. Scales with sqrt(time) for independent returns."""
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, periods_per_year: int, risk_free_rate: float = 0.0) -> float:
    """Annualized mean excess return per unit of volatility."""
    excess = returns - risk_free_rate / periods_per_year
    return float(excess.mean() / excess.std(ddof=1) * np.sqrt(periods_per_year))


def drawdown(returns: pd.Series) -> pd.Series:
    """Fall from the highest value reached so far, as a fraction (0 = at a new high)."""
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax().clip(lower=1.0)  # the starting value counts as a peak
    return wealth / peak - 1


def max_drawdown(returns: pd.Series) -> float:
    """Worst peak-to-trough loss, as a negative fraction."""
    return float(drawdown(returns).min())


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical VaR: the loss exceeded in only (1 - confidence) of periods. Positive = loss."""
    return float(-returns.quantile(1 - confidence))


def conditional_value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """CVaR (expected shortfall): the average loss in the periods at or beyond the VaR."""
    cutoff = returns.quantile(1 - confidence)
    return float(-returns[returns <= cutoff].mean())


def summary(
    returns: pd.Series,
    periods_per_year: int,
    risk_free_rate: float = 0.0,
    var_confidence: float = 0.95,
) -> dict[str, float]:
    return {
        "total_return": total_return(returns),
        "cagr": cagr(returns, periods_per_year),
        "volatility": volatility(returns, periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year, risk_free_rate),
        "max_drawdown": max_drawdown(returns),
        "var": value_at_risk(returns, var_confidence),
        "cvar": conditional_value_at_risk(returns, var_confidence),
    }
