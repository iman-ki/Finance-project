"""Turn target weights into portfolio returns, period by period.

Timing (the no-look-ahead rule): weights decided at the close of period t-1 earn the
asset returns of period t. Trades happen only on rebalance dates; between them the
holdings drift with prices, the way a real portfolio does.

Costs: every trade pays (commission + slippage) on the traded amount. Turnover is the
sum of absolute weight changes, so going from 0% to 100% in one asset is turnover 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REBALANCE_PERIODS = {"weekly": "W", "monthly": "M", "quarterly": "Q", "yearly": "Y"}


@dataclass
class BacktestResult:
    returns: pd.Series  # net of costs, one per period (the first date is the start, not a period)
    gross_returns: pd.Series
    costs: pd.Series  # fraction of capital paid in costs, per period
    turnover: pd.Series
    weights: pd.DataFrame  # weights held during each period

    def equity(self, initial_capital: float) -> pd.Series:
        """Portfolio value over time, starting from initial_capital on the first date."""
        growth = (1 + self.returns).cumprod()
        start = pd.Series([1.0], index=[self.weights.index[0]])
        return initial_capital * pd.concat([start, growth])


def rebalance_dates(index: pd.DatetimeIndex, rule: str) -> np.ndarray:
    """True on dates where the portfolio is reset to target: the last date of each
    calendar period, plus the first date so the portfolio gets invested at all."""
    if rule == "every_period":
        mask = np.ones(len(index), dtype=bool)
    elif rule in REBALANCE_PERIODS:
        periods = index.to_period(REBALANCE_PERIODS[rule])
        mask = np.append(periods[1:] != periods[:-1], True)
    else:
        raise ValueError(
            f"unknown rebalance rule '{rule}'. Use every_period or {list(REBALANCE_PERIODS)}"
        )
    mask[0] = True
    return mask


def run(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    commission_bps: float,
    slippage_bps: float,
    rebalance: str = "monthly",
) -> BacktestResult:
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("prices must be sorted by date with no duplicate dates")
    if not target_weights.index.equals(prices.index) or list(target_weights.columns) != list(
        prices.columns
    ):
        raise ValueError("target_weights must have the same dates and tickers as prices")

    asset_returns = prices.pct_change(fill_method=None).to_numpy()
    targets = target_weights.fillna(0.0).to_numpy()
    trade_now = rebalance_dates(prices.index, rebalance)
    cost_rate = (commission_bps + slippage_bps) / 10_000

    n, m = prices.shape
    held = np.zeros((n, m))
    gross = np.zeros(n)
    turnover = np.zeros(n)
    weights = np.zeros(m)  # current holdings as fractions of capital; the rest is cash

    for t in range(1, n):
        if trade_now[t - 1]:
            turnover[t] = np.abs(targets[t - 1] - weights).sum()
            weights = targets[t - 1].copy()
        period_returns = asset_returns[t]
        if np.isnan(period_returns[weights != 0]).any():
            raise ValueError(f"missing price for a held asset on {prices.index[t].date()}")
        period_returns = np.nan_to_num(period_returns)
        held[t] = weights
        gross[t] = weights @ period_returns
        # Drift: each holding grows with its own return, cash stays flat.
        weights = weights * (1 + period_returns) / (1 + gross[t])

    costs = turnover * cost_rate
    net = (1 - costs) * (1 + gross) - 1  # costs are paid at the trade, before the period's move

    dates = prices.index
    periods = dates[1:]
    return BacktestResult(
        returns=pd.Series(net[1:], index=periods, name="returns"),
        gross_returns=pd.Series(gross[1:], index=periods, name="gross_returns"),
        costs=pd.Series(costs[1:], index=periods, name="costs"),
        turnover=pd.Series(turnover[1:], index=periods, name="turnover"),
        weights=pd.DataFrame(held, index=dates, columns=prices.columns),
    )
