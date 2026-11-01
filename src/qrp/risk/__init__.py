"""Stage 3, risk management: review and limit a strategy's weights before they are traded.

Every module in this folder is imported automatically, so a new risk model is just a new file.
"""

from qrp.core.registry import autodiscover

autodiscover(__name__, __path__)
