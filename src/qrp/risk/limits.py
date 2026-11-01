"""Position limits: the basic rules every portfolio follows before it trades.

Applied in this order, per date:
1. long_only: negative weights (short positions) become 0.
2. max_weight: no single asset above this fraction of capital (or below minus it).
3. max_gross_exposure: if the sum of absolute weights is above this, scale every
   position down by the same factor (1.0 = fully invested, no leverage).

Whatever is cut stays in cash; it is not handed to the other assets.
"""

from __future__ import annotations

import pandas as pd

from qrp.risk.base import RiskModel, risk_models


@risk_models.register("limits")
class Limits(RiskModel):
    def __init__(
        self,
        long_only: bool = True,
        max_weight: float = 1.0,
        max_gross_exposure: float = 1.0,
    ) -> None:
        if max_weight <= 0 or max_gross_exposure <= 0:
            raise ValueError("max_weight and max_gross_exposure must be positive")
        self.long_only = long_only
        self.max_weight = max_weight
        self.max_gross_exposure = max_gross_exposure

    def apply(self, weights: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
        w = weights.fillna(0.0)
        if self.long_only:
            w = w.clip(lower=0.0)
        w = w.clip(lower=-self.max_weight, upper=self.max_weight)
        gross = w.abs().sum(axis=1)
        scale = (self.max_gross_exposure / gross).where(gross > self.max_gross_exposure, 1.0)
        return w.mul(scale, axis=0)
