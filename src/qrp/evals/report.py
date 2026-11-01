"""Write a run's results to a folder: charts (PNG), metrics and returns (CSV), report.md."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files, no window
import matplotlib.pyplot as plt
import pandas as pd

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed order, never cycled

METRIC_LABELS = {
    "total_return": ("Total return", "pct"),
    "cagr": ("CAGR (annual)", "pct"),
    "volatility": ("Volatility (annual)", "pct"),
    "sharpe": ("Sharpe ratio", "num"),
    "max_drawdown": ("Max drawdown", "pct"),
    "var": ("VaR (1 period)", "pct"),
    "cvar": ("CVaR (1 period)", "pct"),
    "total_costs": ("Costs paid (sum, % of capital)", "pct"),
    "final_value": ("Final value", "money"),
}


def _format(value: float, kind: str) -> str:
    if kind == "pct":
        return f"{value:.2%}"
    if kind == "money":
        return f"{value:,.0f}"
    return f"{value:.2f}"


def _style(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=TEXT_PRIMARY, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel, color=TEXT_SECONDARY)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.tick_params(colors=TEXT_SECONDARY, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


def _legend(ax: plt.Axes, count: int) -> None:
    if count >= 2:  # one series is named by the title, no legend box needed
        legend = ax.legend(frameon=False, loc="upper left")
        for text in legend.get_texts():
            text.set_color(TEXT_PRIMARY)


def plot_equity(equity: dict[str, pd.Series], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=SURFACE)
    for (label, series), color in zip(equity.items(), SERIES_COLORS):
        ax.plot(series.index, series.values, color=color, linewidth=2, label=label)
    ax.set_yscale("log")  # equal vertical distance = equal % change, fair over decades
    _style(ax, "Portfolio value (log scale)", "Value")
    _legend(ax, len(equity))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_drawdown(drawdowns: dict[str, pd.Series], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.5), facecolor=SURFACE)
    for (label, series), color in zip(drawdowns.items(), SERIES_COLORS):
        ax.plot(series.index, series.values * 100, color=color, linewidth=2, label=label)
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    _style(ax, "Drawdown from previous peak", "%")
    _legend(ax, len(drawdowns))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def metrics_markdown(metrics: pd.DataFrame) -> str:
    """metrics: one row per metric key, one column per series."""
    header = "| Metric | " + " | ".join(metrics.columns) + " |"
    divider = "|---|" + "---:|" * len(metrics.columns)
    rows = []
    for key, values in metrics.iterrows():
        label, kind = METRIC_LABELS.get(key, (key, "num"))
        rows.append(f"| {label} | " + " | ".join(_format(v, kind) for v in values) + " |")
    return "\n".join([header, divider, *rows])


def write_report(
    out_dir: Path,
    title: str,
    returns: dict[str, pd.Series],
    equity: dict[str, pd.Series],
    drawdowns: dict[str, pd.Series],
    metrics: pd.DataFrame,
    details: dict[str, str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_equity(equity, out_dir / "equity.png")
    plot_drawdown(drawdowns, out_dir / "drawdown.png")
    metrics.to_csv(out_dir / "metrics.csv")
    pd.DataFrame(returns).to_csv(out_dir / "returns.csv")

    lines = [f"# {title}", ""]
    lines += [f"- **{key}:** {value}" for key, value in details.items()]
    lines += ["", "## Metrics", "", metrics_markdown(metrics), ""]
    lines += [
        "## Charts",
        "",
        "![Portfolio value](equity.png)",
        "",
        "![Drawdown](drawdown.png)",
        "",
    ]
    disclaimer = "Backtest results are simulations on historical data, not predictions."
    lines += [f"_{disclaimer} Not financial advice._", ""]
    report = out_dir / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report
