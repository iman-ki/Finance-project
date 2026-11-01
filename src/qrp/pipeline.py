"""One full research run, driven by config:

1. data  ->  2. strategy creation  ->  3. risk management  ->  4. simulation  ->  5. evals
(prices)     (target weights)          (allowed weights)        (returns, costs)   (metrics, report)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from qrp import backtest
from qrp.core.config import PERIOD_NAMES, PERIODS_PER_YEAR, load_env, resolve_path
from qrp.data import providers as _load_providers  # noqa: F401  (registers every provider)
from qrp.data.base import providers
from qrp.evals import metrics, write_report
from qrp.risk.base import RiskModel, risk_models
from qrp.strategies.base import Strategy, strategies
from qrp.strategies.buy_and_hold import BuyAndHold


@dataclass
class Simulation:
    """Everything a run produced, in memory. The report and the app both read from this."""

    prices: pd.DataFrame
    runs: dict[str, backtest.BacktestResult]  # label -> result; strategy first, then benchmark
    target_weights: pd.DataFrame  # what the strategy asked for (stage 2)
    allowed_weights: pd.DataFrame  # what risk management let through (stage 3)
    metrics: pd.DataFrame  # one row per metric, one column per run
    details: dict[str, str]
    title: str
    initial_capital: float

    def equity(self) -> dict[str, pd.Series]:
        return {label: r.equity(self.initial_capital) for label, r in self.runs.items()}

    def drawdowns(self) -> dict[str, pd.Series]:
        return {label: metrics.drawdown(r.returns) for label, r in self.runs.items()}

    def risk_adjusted_dates(self) -> int:
        """How many dates risk management changed the strategy's weights."""
        changed = ~np.isclose(self.target_weights.fillna(0.0), self.allowed_weights)
        return int(changed.any(axis=1).sum())


# ---------------------------------------------------------------- 1. data


def load_prices(config: dict[str, Any], refresh: bool = False) -> pd.DataFrame:
    """Prices for the universe plus the benchmark, from the configured provider."""
    load_env()
    data_cfg, universe = config["data"], config["universe"]
    provider = providers.get(data_cfg["provider"])(
        frequency=data_cfg["frequency"],
        raw_path=resolve_path(data_cfg["raw_path"]),
        cache_max_age_hours=data_cfg["cache_max_age_hours"],
        refresh=refresh,
    )
    tickers = list(dict.fromkeys([*universe["tickers"], universe["benchmark"]]))
    return provider.get_prices(tickers, data_cfg["start"], data_cfg.get("end"))


def common_history(prices: pd.DataFrame) -> pd.DataFrame:
    """Start on the first date every ticker has a price, so the strategy and the benchmark
    are measured over the same period (no one sits in cash waiting for a younger asset)."""
    complete = prices.notna().all(axis=1)
    if not complete.any():
        raise ValueError("the tickers have no date in common")
    return prices.loc[complete.idxmax() :]


# ---------------------------------------------------------------- the run


def run(config: dict[str, Any], config_path: Path | None = None, refresh: bool = False) -> Path:
    """Run every stage and return the path of the written report."""
    return save_report(simulate(config, refresh=refresh), config, config_path)


def simulate(
    config: dict[str, Any], refresh: bool = False, prices: pd.DataFrame | None = None
) -> Simulation:
    """Stages 1 to 5 in memory. Pass `prices` to skip loading."""
    data_cfg, universe = config["data"], config["universe"]
    bt_cfg, evals_cfg = config["backtest"], config["evals"]
    benchmark = universe["benchmark"]

    # 1. Data
    if prices is None:
        prices = load_prices(config, refresh=refresh)
    prices = common_history(prices)
    universe_prices = prices[universe["tickers"]]

    # 2. Strategy creation
    strategy_cfg = config["strategy"]
    strategy: Strategy = strategies.get(strategy_cfg["name"])(**strategy_cfg.get("params", {}))
    target = strategy.target_weights(universe_prices)

    # 3. Risk management
    risk_cfg = config["risk_management"]
    risk_model: RiskModel = risk_models.get(risk_cfg["model"])(**risk_cfg.get("params", {}))
    allowed = risk_model.apply(target, universe_prices)

    # 4. Simulation. The benchmark is a reference, so it is held as-is.
    strategy_label = _describe(strategy_cfg)
    runs = {
        strategy_label: _simulate(universe_prices, allowed, bt_cfg),
        f"Benchmark: {benchmark}": _simulate(
            prices[[benchmark]], BuyAndHold(benchmark).target_weights(prices[[benchmark]]), bt_cfg
        ),
    }
    if _same(*runs.values()):  # strategy *is* the benchmark: one line, not two on top of each other
        runs = {strategy_label: runs[strategy_label]}

    # 5. Evals
    periods_per_year = PERIODS_PER_YEAR[data_cfg["frequency"]]
    capital = bt_cfg["initial_capital"]
    table = {}
    for label, result in runs.items():
        row = metrics.summary(
            result.returns,
            periods_per_year,
            evals_cfg["risk_free_rate"],
            evals_cfg["var_confidence"],
        )
        row["total_costs"] = float(result.costs.sum())
        row["final_value"] = float(result.equity(capital).iloc[-1])
        table[label] = row

    sim = Simulation(
        prices=prices,
        runs=runs,
        target_weights=target,
        allowed_weights=allowed,
        metrics=pd.DataFrame(table),
        details={},
        title=f"Backtest: {strategy_label}",
        initial_capital=capital,
    )
    first, last = prices.index[0].date(), prices.index[-1].date()
    period = PERIOD_NAMES[data_cfg["frequency"]]
    sim.details = {
        "Data": f"{data_cfg['provider']}, {data_cfg['frequency']} adjusted close",
        "Period": f"{first} to {last} ({len(prices) - 1} {data_cfg['frequency']} periods)",
        "Universe": ", ".join(universe["tickers"]),
        "Benchmark": benchmark,
        "Strategy": strategy_label,
        "Risk management": _describe({"name": risk_cfg["model"], **risk_cfg}, named=True),
        "Risk adjustments": f"weights changed on {sim.risk_adjusted_dates()} of {len(prices)} dates",
        "Initial capital": f"{capital:,.0f}",
        "Costs": f"{bt_cfg['commission_bps']} bp commission + {bt_cfg['slippage_bps']} bp slippage per trade",
        "Rebalance": bt_cfg["rebalance"],
        "Risk-free rate": f"{evals_cfg['risk_free_rate']:.2%} per year",
        "VaR / CVaR": f"historical, {evals_cfg['var_confidence']:.0%} confidence, one-{period} horizon",
    }
    return sim


def save_report(sim: Simulation, config: dict[str, Any], config_path: Path | None = None) -> Path:
    """Write the report folder, including the exact config behind the result."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = resolve_path(config["evals"]["output_path"]) / f"{stamp}_{config['strategy']['name']}"
    report = write_report(
        out_dir,
        title=sim.title,
        returns={label: r.returns for label, r in sim.runs.items()},
        equity=sim.equity(),
        drawdowns=sim.drawdowns(),
        metrics=sim.metrics,
        details=sim.details,
    )
    if config_path is not None:
        shutil.copy(config_path, out_dir / "config.yaml")
    else:
        text = yaml.safe_dump(config, sort_keys=False)
        (out_dir / "config.yaml").write_text(text, encoding="utf-8")
    return report


# ---------------------------------------------------------------- helpers


def _simulate(prices: pd.DataFrame, weights: pd.DataFrame, bt_cfg: dict) -> backtest.BacktestResult:
    keep = prices.notna().any(axis=1)
    return backtest.run(
        prices[keep],
        weights[keep],
        commission_bps=bt_cfg["commission_bps"],
        slippage_bps=bt_cfg["slippage_bps"],
        rebalance=bt_cfg["rebalance"],
    )


def _same(a: backtest.BacktestResult, b: backtest.BacktestResult) -> bool:
    return a.returns.index.equals(b.returns.index) and np.allclose(a.returns, b.returns)


def _describe(cfg: dict, named: bool = False) -> str:
    items = cfg.get("params", {}).items()
    params = ", ".join(f"{k}={v}" if named else f"{v}" for k, v in items)
    return f"{cfg['name']}({params})" if params else cfg["name"]
