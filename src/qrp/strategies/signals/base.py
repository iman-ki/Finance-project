"""Contract every signal must follow. This is where your future math lives."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from qrp.core.registry import Registry

signals = Registry("signal")


class Signal(ABC):
    """Turns prices into scores.

    Contract: input and output share the same shape (dates x tickers). A higher
    score means "more attractive". The value on date t may only use data up to
    and including t (no look-ahead).
    """

    @abstractmethod
    def compute(self, prices: pd.DataFrame) -> pd.DataFrame: ...
