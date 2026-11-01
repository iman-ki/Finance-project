"""Signals: math plugins that score assets. Building blocks for strategies (stage 2).

Every module in this folder is imported automatically, so a new signal is just a new file.
"""

from qrp.core.registry import autodiscover

autodiscover(__name__, __path__)
