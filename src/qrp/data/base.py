"""Contract every data source must follow."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from qrp.core.registry import Registry

providers = Registry("data provider")


class DataProvider(ABC):
    """Fetches daily price data.

    Contract: returns a DataFrame indexed by date (one row per trading day),
    one column per ticker, holding adjusted close prices. Anything provider-specific
    (column names, adjustments, API quirks) is handled inside the provider.
    """

    @abstractmethod
    def get_prices(
        self, tickers: list[str], start: str, end: str | None = None
    ) -> pd.DataFrame: ...
