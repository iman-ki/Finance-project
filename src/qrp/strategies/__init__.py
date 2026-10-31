"""Strategies: turn signals into target portfolio weights.

Every module in this folder is imported automatically, so a new strategy is just a new file.
"""

from qrp.core.registry import autodiscover

autodiscover(__name__, __path__)
