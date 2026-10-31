"""Concrete data providers (Alpha Vantage, Tiingo, FRED, SEC EDGAR...). One file per source.

Every module in this folder is imported automatically, so a new provider is just a new file.
"""

from qrp.core.registry import autodiscover

autodiscover(__name__, __path__)
