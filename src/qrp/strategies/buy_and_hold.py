"""Buy and hold one asset. The baseline every other strategy has to beat."""

from __future__ import annotations

import pandas as pd

from qrp.strategies.base import Strategy, strategies


@strategies.register("buy_and_hold")
class BuyAndHold(Strategy):
    def __init__(self, ticker: str = "SPY") -> None:
        self.ticker = ticker

    def target_weights(self, prices: pd.DataFrame) -> pd.DataFrame:
        if self.ticker not in prices.columns:
            raise KeyError(f"buy_and_hold: '{self.ticker}' is not in the price data")
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        # Fully invested from the first date the asset has a price.
        weights[self.ticker] = prices[self.ticker].notna().astype(float)
        return weights
