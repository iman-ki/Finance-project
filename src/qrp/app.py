"""Interactive front end. Start it with `python -m qrp app`.

Everything here is a view over the same pipeline the CLI uses (qrp.pipeline): the sidebar
builds a config dict, the pipeline runs it, the tabs draw the result. No numbers are
computed only in the app.
"""

from __future__ import annotations

import inspect

import altair as alt
import pandas as pd
import streamlit as st

from qrp import pipeline
from qrp.core.config import PERIOD_NAMES, PERIODS_PER_YEAR, load_config
from qrp.data.base import providers
from qrp.evals import metrics as ev
from qrp.risk.base import risk_models
from qrp.strategies.base import strategies
from qrp.strategies.signals.base import signals

alt.data_transformers.disable_max_rows()

# Reference palette (dataviz skill), light mode. Categorical slots in fixed order.
SERIES_COLORS = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]
OTHER_COLOR = "#a3a29c"
TEXT_SECONDARY = "#52514e"
DIVERGING = ["#e34948", "#f0efec", "#2a78d6"]  # -1 red, 0 gray, +1 blue

PRESET_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "XOM", "JNJ", "GLD", "TLT"]
FREQUENCIES = list(PERIODS_PER_YEAR)
REBALANCE_RULES = ["every_period", "weekly", "monthly", "quarterly", "yearly"]

ROADMAP = [
    ("Foundations: data provider, returns, risk metrics, tests", "done"),
    ("Backtest engine: weights to P&L with costs, no look-ahead", "done"),
    ("Benchmarking: correlation, beta/alpha, rolling metrics", "next"),
    ("Validation: walk-forward testing, overfitting corrections", "planned"),
    ("Portfolio and risk layer: risk parity, stress tests", "planned"),
    ("Fundamentals and filings: SEC EDGAR, LLM-assisted analysis", "planned"),
    ("Advanced plugins: factor, stochastic, quantum-inspired models", "planned"),
]
STATUS_ICONS = {"done": "✅ Done", "next": "▶️ Next", "planned": "⏳ Planned"}

st.set_page_config(page_title="QRP · Quant Research Platform", page_icon="📈", layout="wide")


# ---------------------------------------------------------------- data


@st.cache_data(show_spinner="Loading prices...")
def load_prices(provider: str, frequency: str, tickers: tuple[str, ...], refresh: bool):
    config = load_config()
    config["data"].update(provider=provider, frequency=frequency, start="1900-01-01", end=None)
    config["universe"] = {"tickers": list(tickers), "benchmark": tickers[0]}
    return pipeline.load_prices(config, refresh=refresh)


# ---------------------------------------------------------------- charts


def color_scale(names: list[str]) -> alt.Scale:
    """Color follows the entity's position in `names`; past 8 series everything is gray."""
    colors = [
        SERIES_COLORS[i] if i < len(SERIES_COLORS) else OTHER_COLOR for i in range(len(names))
    ]
    return alt.Scale(domain=names, range=colors)


def line_chart(
    series: dict[str, pd.Series],
    y_title: str,
    fmt: str,
    log: bool = False,
    height: int = 340,
) -> alt.LayerChart:
    """Lines with a hover crosshair: one tooltip lists every series at the hovered date."""
    names = list(series)
    wide = pd.DataFrame(series)
    wide.index.name = "date"
    long = wide.reset_index().melt("date", var_name="series", value_name="value").dropna()
    keys = {name: f"s{i}" for i, name in enumerate(names)}  # safe field names for tooltips
    flat = wide.rename(columns=keys).reset_index()

    x = alt.X("date:T", title=None, axis=alt.Axis(grid=False, labelColor=TEXT_SECONDARY))
    y = alt.Y(
        "value:Q",
        title=y_title,
        scale=alt.Scale(type="log") if log else alt.Scale(zero=False),
        axis=alt.Axis(format=fmt, labelColor=TEXT_SECONDARY, titleColor=TEXT_SECONDARY),
    )
    color = alt.Color(
        "series:N",
        scale=color_scale(names),
        legend=alt.Legend(orient="top", title=None, labelLimit=320) if len(names) > 1 else None,
    )
    hover = alt.selection_point(nearest=True, on="pointerover", fields=["date"], empty=False)

    lines = alt.Chart(long).mark_line(strokeWidth=2).encode(x=x, y=y, color=color)
    dots = (
        alt.Chart(long)
        .mark_circle(size=70, stroke="white", strokeWidth=2)
        .encode(x="date:T", y="value:Q", color=color)
        .transform_filter(hover)
    )
    rule = (
        alt.Chart(flat)
        .mark_rule(color=TEXT_SECONDARY, strokeWidth=1)
        .encode(
            x="date:T",
            opacity=alt.condition(hover, alt.value(0.5), alt.value(0)),
            tooltip=[alt.Tooltip("date:T", title="Date", format="%Y-%m-%d")]
            + [alt.Tooltip(f"{keys[n]}:Q", title=n, format=fmt) for n in names],
        )
        .add_params(hover)
    )
    return (lines + dots + rule).properties(height=height)


def yearly_bars(returns: dict[str, pd.Series]) -> alt.Chart:
    names = list(returns)
    table = pd.DataFrame({n: (1 + r).groupby(r.index.year).prod() - 1 for n, r in returns.items()})
    table.index.name = "year"
    long = table.reset_index().melt("year", var_name="series", value_name="return")
    return (
        alt.Chart(long)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0, labelColor=TEXT_SECONDARY)),
            xOffset=alt.XOffset("series:N", sort=names),
            y=alt.Y(
                "return:Q", title="Return", axis=alt.Axis(format="%", labelColor=TEXT_SECONDARY)
            ),
            color=alt.Color(
                "series:N",
                scale=color_scale(names),
                legend=alt.Legend(orient="top", title=None, labelLimit=320)
                if len(names) > 1
                else None,
            ),
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("return:Q", title="Return", format=".2%"),
            ],
        )
        .properties(height=300)
    )


def holdings_chart(weights: pd.DataFrame) -> alt.Chart:
    held = weights.loc[:, (weights != 0).any()].rename_axis("date")
    names = list(held.columns)
    long = held.reset_index().melt("date", var_name="ticker", value_name="weight")
    return (
        alt.Chart(long)
        .mark_area()
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(grid=False, labelColor=TEXT_SECONDARY)),
            y=alt.Y("weight:Q", title="Weight", stack=True, axis=alt.Axis(format="%")),
            color=alt.Color(
                "ticker:N", scale=color_scale(names), legend=alt.Legend(orient="top", title=None)
            ),
            tooltip=[
                alt.Tooltip("date:T", format="%Y-%m-%d"),
                "ticker:N",
                alt.Tooltip("weight:Q", format=".1%"),
            ],
        )
        .properties(height=220)
    )


def correlation_heatmap(corr: pd.DataFrame) -> alt.LayerChart:
    names = list(corr.columns)
    long = corr.rename_axis("a").reset_index().melt("a", var_name="b", value_name="corr")
    base = alt.Chart(long).encode(
        x=alt.X("b:N", sort=names, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("a:N", sort=names, title=None),
    )
    cells = base.mark_rect(stroke="white", strokeWidth=2, cornerRadius=4).encode(
        color=alt.Color(
            "corr:Q",
            scale=alt.Scale(domain=[-1, 0, 1], range=DIVERGING),
            legend=alt.Legend(title="Correlation", orient="right"),
        ),
        tooltip=[
            alt.Tooltip("a:N", title="Asset"),
            alt.Tooltip("b:N", title="vs"),
            alt.Tooltip("corr:Q", title="Correlation", format=".2f"),
        ],
    )
    labels = base.mark_text(fontSize=12, color="#0b0b0b").encode(
        text=alt.Text("corr:Q", format=".2f")
    )
    size = 60 * len(names) + 40
    return (cells + labels).properties(width=size, height=size)


# ---------------------------------------------------------------- formatting


def pct(v: float) -> str:
    return f"{v:.2%}"


METRIC_ROWS = {
    "total_return": ("Total return", pct),
    "cagr": ("CAGR (annual)", pct),
    "volatility": ("Volatility (annual)", pct),
    "sharpe": ("Sharpe ratio", lambda v: f"{v:.2f}"),
    "max_drawdown": ("Max drawdown", pct),
    "var": ("VaR (1 period)", pct),
    "cvar": ("CVaR (1 period)", pct),
    "total_costs": ("Costs paid", pct),
    "final_value": ("Final value", lambda v: f"{v:,.0f}"),
}


def metrics_table(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = {
        label: [fmt(v) for v in metrics.loc[key]]
        for key, (label, fmt) in METRIC_ROWS.items()
        if key in metrics.index
    }
    return pd.DataFrame(rows, index=metrics.columns).T


def kpi(col, label: str, value: float, bench: float | None, kind: str, better: str = "higher"):
    shown = {"pct": pct(value), "num": f"{value:.2f}", "money": f"{value:,.0f}"}[kind]
    delta = None
    if bench is not None:
        diff = value - bench
        delta = {
            "pct": f"{diff * 100:+.2f} pp vs benchmark",
            "num": f"{diff:+.2f} vs benchmark",
            "money": f"{diff:+,.0f} vs benchmark",
        }[kind]
    col.metric(label, shown, delta, delta_color="normal" if better == "higher" else "inverse")


# ---------------------------------------------------------------- sidebar


def plugin_inputs(cls: type, tickers: list[str], saved: dict, prefix: str) -> dict:
    """One widget per constructor argument, so a new plugin gets its controls for free."""
    params = {}
    for name, p in inspect.signature(cls.__init__).parameters.items():
        if name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        default = saved.get(name, None if p.default is p.empty else p.default)
        label = name.replace("_", " ").capitalize()
        if name == "ticker":
            index = tickers.index(default) if default in tickers else 0
            params[name] = st.selectbox(label, tickers, index=index, key=f"{prefix}_{name}")
        elif isinstance(default, bool):
            params[name] = st.checkbox(label, value=default, key=f"{prefix}_{name}")
        elif isinstance(default, int):
            params[name] = int(
                st.number_input(label, value=default, step=1, key=f"{prefix}_{name}")
            )
        elif isinstance(default, float):
            params[name] = float(st.number_input(label, value=default, key=f"{prefix}_{name}"))
        else:
            params[name] = st.text_input(
                label, value="" if default is None else str(default), key=f"{prefix}_{name}"
            )
    return params


def sidebar(cfg: dict) -> dict:
    """Collect every setting into a config dict shaped like config/default.yaml."""
    with st.sidebar:
        st.header("Experiment")

        st.subheader("1 · Data")
        names = providers.names()
        provider = st.selectbox("Provider", names, index=names.index(cfg["data"]["provider"]))
        frequency = st.selectbox(
            "Frequency", FREQUENCIES, index=FREQUENCIES.index(cfg["data"]["frequency"])
        )
        if provider == "alphavantage" and frequency == "daily":
            st.warning("Alpha Vantage's free key has no daily history. Use weekly or monthly.")

        st.subheader("Universe")
        extra = st.text_input("Add tickers", placeholder="e.g. NVDA, VTI", help="Comma-separated")
        custom = [t.strip().upper() for t in extra.split(",") if t.strip()]
        options = list(dict.fromkeys(PRESET_TICKERS + cfg["universe"]["tickers"] + custom))
        tickers = st.multiselect(
            "Tickers", options, default=list(dict.fromkeys(cfg["universe"]["tickers"] + custom))
        )
        benchmark = st.selectbox(
            "Benchmark", options, index=options.index(cfg["universe"]["benchmark"])
        )

        st.subheader("2 · Strategy creation")
        strategy_names = strategies.names()
        name = st.selectbox(
            "Strategy",
            strategy_names,
            index=strategy_names.index(cfg["strategy"]["name"]),
        )
        saved = cfg["strategy"].get("params", {}) if name == cfg["strategy"]["name"] else {}
        params = plugin_inputs(strategies.get(name), tickers or [benchmark], saved, "strategy")

        st.subheader("3 · Risk management")
        rm = cfg["risk_management"]
        model_names = risk_models.names()
        model = st.selectbox("Risk model", model_names, index=model_names.index(rm["model"]))
        saved_rm = rm.get("params", {}) if model == rm["model"] else {}
        risk_params = plugin_inputs(risk_models.get(model), tickers, saved_rm, "risk")

        st.subheader("4 · Simulation")
        bt = cfg["backtest"]
        capital = st.number_input(
            "Initial capital", value=float(bt["initial_capital"]), step=1000.0
        )
        commission = st.number_input(
            "Commission (bp per trade)", value=float(bt["commission_bps"]), step=0.5
        )
        slippage = st.number_input(
            "Slippage (bp per trade)", value=float(bt["slippage_bps"]), step=0.5
        )
        rebalance = st.selectbox(
            "Rebalance", REBALANCE_RULES, index=REBALANCE_RULES.index(bt["rebalance"])
        )

        st.subheader("5 · Evals")
        ev_cfg = cfg["evals"]
        rf = st.number_input(
            "Risk-free rate (% per year)", value=ev_cfg["risk_free_rate"] * 100, step=0.25
        )
        confidence = st.slider("VaR confidence", 0.80, 0.99, float(ev_cfg["var_confidence"]), 0.01)

    return {
        "data": {**cfg["data"], "provider": provider, "frequency": frequency},
        "universe": {"tickers": tickers, "benchmark": benchmark},
        "strategy": {"name": name, "params": params},
        "backtest": {
            "initial_capital": capital,
            "commission_bps": commission,
            "slippage_bps": slippage,
            "rebalance": rebalance,
        },
        "risk_management": {"model": model, "params": risk_params},
        "evals": {**cfg["evals"], "risk_free_rate": rf / 100, "var_confidence": confidence},
    }


# ---------------------------------------------------------------- tabs


def project_map_tab() -> None:
    st.subheader("Where things are, and where they will go")
    st.caption(
        "Solid boxes exist today; dashed boxes are planned. Plugin names come live from the registries."
    )

    def node(key, title, items, built):
        listing = "\\n".join(items) if items else "(none yet)"
        style = (
            'style="rounded,filled", fillcolor="#cde2fb", color="#2a78d6"'
            if built
            else 'style="rounded,dashed", color="#a3a29c", fontcolor="#52514e"'
        )
        return f'{key} [label="{title}\\n\\n{listing}", {style}];'

    dot = "\n".join(
        [
            "digraph {",
            'rankdir=LR; bgcolor="transparent";',
            'node [shape=box, fontname="Helvetica", fontsize=11, penwidth=1.5, margin="0.2,0.12"];',
            'edge [color="#52514e", arrowsize=0.7];',
            node("data", "1 · DATA", providers.names(), True),
            node(
                "strategies",
                "2 · STRATEGY CREATION",
                [*strategies.names(), "signals: " + (", ".join(signals.names()) or "none yet")],
                True,
            ),
            node("risk", "3 · RISK MANAGEMENT", risk_models.names(), True),
            node("backtest", "4 · SIMULATION", ["costs, drift,", "no look-ahead"], True),
            node(
                "evals",
                "5 · EVALS",
                ["CAGR, volatility, Sharpe,", "drawdown, VaR, CVaR,", "reports, this app"],
                True,
            ),
            node("fundamentals", "FUNDAMENTALS", ["SEC EDGAR", "LLM analysis"], False),
            node(
                "signals_next", "MORE SIGNALS", ["momentum, factors,", "stochastic models"], False
            ),
            node(
                "risk_next",
                "MORE RISK MODELS",
                ["volatility targeting,", "risk parity, stress tests"],
                False,
            ),
            node("bench", "BENCHMARKING", ["beta / alpha", "rolling metrics"], False),
            node("validation", "VALIDATION", ["walk-forward", "overfitting checks"], False),
            "data -> strategies -> risk -> backtest -> evals;",
            "fundamentals -> data [style=dashed];",
            "signals_next -> strategies [style=dashed];",
            "risk_next -> risk [style=dashed];",
            "evals -> bench [style=dashed];",
            "evals -> validation [style=dashed];",
            "}",
        ]
    )
    st.graphviz_chart(dot, width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Roadmap")
        for i, (phase, status) in enumerate(ROADMAP, start=1):
            st.markdown(f"**{i}.** {phase} — {STATUS_ICONS[status]}")
    with right:
        st.markdown("#### Rules that keep results honest")
        st.markdown(
            "- **No look-ahead:** weights decided at a close earn the *next* period's return.\n"
            "- **Risk management before trading:** every strategy's weights pass the limits.\n"
            "- **Costs are never zero:** commission + slippage on every trade.\n"
            "- **Holdings drift** between rebalances, like a real portfolio.\n"
            "- **Same period for everyone:** runs start when every ticker has data.\n"
            "- **Config over code:** every saved report keeps its exact settings.\n"
            "- **Everything numeric is tested** against hand-computed examples."
        )
        st.markdown("#### Add a plugin")
        st.code(
            "# src/qrp/strategies/my_idea.py\n"
            "from qrp.strategies.base import Strategy, strategies\n\n"
            '@strategies.register("my_idea")\n'
            "class MyIdea(Strategy):\n"
            "    def __init__(self, lookback: int = 12): ...\n"
            "    def target_weights(self, prices): ...",
            language="python",
        )
        st.caption("It appears in the sidebar automatically, with one input per argument.")


def backtest_tab(sim: pipeline.Simulation, config: dict) -> None:
    labels = list(sim.runs)
    strat, bench = labels[0], (labels[1] if len(labels) > 1 else None)
    m = sim.metrics

    st.subheader(sim.title)
    st.caption(sim.details["Period"])
    adjusted = sim.risk_adjusted_dates()
    if adjusted:
        st.warning(
            f"Risk management changed the strategy's weights on {adjusted:,} of "
            f"{len(sim.prices):,} dates ({sim.details['Risk management']})."
        )
    if bench is None:
        st.info(
            "The strategy is identical to the benchmark, so only one line is shown. "
            "Pick another ticker or strategy in the sidebar to compare."
        )

    def b(key):
        return m.loc[key, bench] if bench else None

    cols = st.columns(5)
    kpi(cols[0], "CAGR", m.loc["cagr", strat], b("cagr"), "pct")
    kpi(cols[1], "Volatility", m.loc["volatility", strat], b("volatility"), "pct", better="lower")
    kpi(cols[2], "Sharpe", m.loc["sharpe", strat], b("sharpe"), "num")
    kpi(cols[3], "Max drawdown", m.loc["max_drawdown", strat], b("max_drawdown"), "pct")
    kpi(cols[4], "Final value", m.loc["final_value", strat], b("final_value"), "money")

    log = st.toggle(
        "Log scale", value=True, help="Equal distances = equal % changes. Fairer over decades."
    )
    st.altair_chart(line_chart(sim.equity(), "Portfolio value", ",.0f", log=log), width="stretch")
    st.altair_chart(
        line_chart(sim.drawdowns(), "Drawdown from peak", ".1%", height=240), width="stretch"
    )

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Calendar-year returns")
        st.altair_chart(
            yearly_bars({label: r.returns for label, r in sim.runs.items()}),
            width="stretch",
        )
        st.caption("First and last years are partial.")
    with right:
        st.markdown("#### All metrics")
        st.dataframe(metrics_table(m), width="stretch")
        period = PERIOD_NAMES[config["data"]["frequency"]]
        st.caption(
            f"VaR / CVaR: historical, {config['evals']['var_confidence']:.0%} confidence, one-{period} loss."
        )

    with st.expander("Holdings (after risk management) and trading"):
        result = sim.runs[strat]
        st.altair_chart(holdings_chart(result.weights), width="stretch")
        trades = int((result.turnover > 0).sum())
        st.markdown(
            f"**{trades}** rebalancing trades · average turnover per trade "
            f"**{result.turnover[result.turnover > 0].mean():.1%}** · total costs **{result.costs.sum():.3%}** of capital"
        )

    with st.expander("Run details"):
        st.table(pd.Series(sim.details, name="Value"))

    if st.button("💾 Save this run as a report"):
        path = pipeline.save_report(sim, config)
        st.success(f"Saved to {path.parent}")


def data_tab(prices: pd.DataFrame, frequency: str) -> None:
    tickers = list(prices.columns)
    if len(tickers) > len(SERIES_COLORS):
        st.warning(
            f"Showing the first {len(SERIES_COLORS)} tickers; colors can't stay distinct past that."
        )
        tickers = tickers[: len(SERIES_COLORS)]
    prices = prices[tickers]
    ppy = PERIODS_PER_YEAR[frequency]

    st.subheader("Growth of 100")
    st.caption(
        "Full history of each ticker, from its own first date (the date slider applies to the "
        "backtest). Daily data is drawn weekly to keep the chart fast."
    )
    shown = prices.resample("W-FRI").last() if frequency == "daily" else prices
    growth = {t: 100 * s.dropna() / s.dropna().iloc[0] for t, s in shown.items()}
    st.altair_chart(line_chart(growth, "Value of 100 invested", ",.0f", log=True), width="stretch")

    rows = {}
    for t in tickers:
        s = prices[t].dropna()
        r = s.pct_change().dropna()
        rows[t] = {
            "First date": s.index[0].date(),
            "Last price": f"{s.iloc[-1]:,.2f}",
            "CAGR": pct(ev.cagr(r, ppy)),
            "Volatility": pct(ev.volatility(r, ppy)),
            "Sharpe": f"{ev.sharpe_ratio(r, ppy):.2f}",
            "Max drawdown": pct(ev.max_drawdown(r)),
        }
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Each ticker over its own history")
        st.dataframe(pd.DataFrame(rows).T, width="stretch")
    with right:
        if len(tickers) > 1:
            common = pipeline.common_history(prices)
            st.markdown("#### Correlation of returns")
            st.caption(f"Over the common period from {common.index[0].date()}.")
            corr = common.pct_change(fill_method=None).corr()
            st.altair_chart(correlation_heatmap(corr), width="content")


# ---------------------------------------------------------------- page


def main() -> None:
    cfg = load_config()
    config = sidebar(cfg)

    st.title("Quant Research Platform")
    st.caption(
        "1 data → 2 strategy creation → 3 risk management → 4 simulation → 5 evals"
        "  ·  not financial advice"
    )
    tab_bt, tab_data, tab_map = st.tabs(["📈 Backtest", "🗂️ Data", "🧭 Project map"])

    with tab_map:
        project_map_tab()

    tickers = config["universe"]["tickers"]
    if not tickers:
        with tab_bt:
            st.info("Pick at least one ticker in the sidebar.")
        return

    all_tickers = tuple(dict.fromkeys([*tickers, config["universe"]["benchmark"]]))
    refresh = st.session_state.pop("refresh", False)
    try:
        prices = load_prices(
            config["data"]["provider"], config["data"]["frequency"], all_tickers, refresh
        )
    except Exception as exc:  # noqa: BLE001  show provider problems (network, bad ticker, quota)
        with tab_bt:
            st.error(f"Could not load prices: {exc}")
        return

    with st.sidebar:
        st.subheader("Period")
        common = pipeline.common_history(prices)
        first, last = common.index[0].date(), common.index[-1].date()
        start, end = st.slider("Dates", first, last, (first, last), format="YYYY-MM-DD")
        st.caption(f"Common history starts {first}: every ticker has data from then on.")
        if st.button("🔄 Re-download data", help="Ignore saved copies and fetch fresh prices"):
            st.cache_data.clear()
            st.session_state["refresh"] = True
            st.rerun()
    config["data"].update(start=str(start), end=str(end))
    window = prices.loc[str(start) : str(end)]

    with tab_bt:
        try:
            sim = pipeline.simulate(config, prices=window)
        except Exception as exc:  # noqa: BLE001  show any failure in the page, not a crash
            st.error(f"Backtest failed: {exc}")
        else:
            backtest_tab(sim, config)

    with tab_data:
        data_tab(prices, config["data"]["frequency"])


main()
