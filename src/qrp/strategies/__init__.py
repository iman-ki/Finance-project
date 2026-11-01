"""Stage 2, strategy creation: turn prices (and signals) into target portfolio weights.

Signals, the math building blocks strategies use, live in `strategies/signals/`.

Every module in this folder is imported automatically, so a new strategy is just a new file.
"""

from qrp.core.registry import autodiscover

autodiscover(__name__, __path__)
