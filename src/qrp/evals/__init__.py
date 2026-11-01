"""Stage 5, evals: judge a simulated run. Performance and risk metrics, reports and charts."""

from qrp.evals.metrics import summary
from qrp.evals.report import write_report

__all__ = ["summary", "write_report"]
