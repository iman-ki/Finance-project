"""Contract every strategy must follow."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from qrp.core.registry import Registry

strategies = Registry("strategy")


class Strategy(ABC):
    """Decides how much of each asset to hold.

    Contract: given prices (dates x tickers), return target weights with the same
    shape. Each row is the desired portfolio at the close of that date; weights
    are fractions of capital (1.0 = fully invested). The backtester applies them
    to the NEXT period's returns, which keeps look-ahead out by construction.
    """

    @abstractmethod
    def target_weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        ...
