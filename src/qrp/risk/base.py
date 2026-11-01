"""Contract every risk model must follow. Stage 3: between strategy creation and simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from qrp.core.registry import Registry

risk_models = Registry("risk model")


class RiskModel(ABC):
    """Reviews a strategy's target weights before anything is traded.

    Contract: takes the strategy's weights and the prices (both dates x tickers) and returns
    the weights that are allowed, same shape. It may cut, cap or scale positions, never add
    new ones. Like a strategy, the row for date t may only use data up to t.
    """

    @abstractmethod
    def apply(self, weights: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame: ...
