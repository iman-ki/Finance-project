"""One full research run: data -> strategy -> backtest -> risk -> report, driven by config."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qrp import backtest
from qrp.core.config import PERIODS_PER_YEAR, load_env, resolve_path
from qrp.data import providers as _load_providers  # noqa: F401  (registers every provider)
from qrp.data.base import providers
from qrp.reporting import write_report
from qrp.risk import metrics as risk
from qrp.strategies.base import strategies
from qrp.strategies.buy_and_hold import BuyAndHold


def run(config: dict[str, Any], config_path: Path | None = None, refresh: bool = False) -> Path:
    """Run the pipeline and return the path of the written report."""
    load_env()
    data_cfg, universe = config["data"], config["universe"]
    bt_cfg, risk_cfg = config["backtest"], config["risk"]

    provider = providers.get(data_cfg["provider"])(
        frequency=data_cfg["frequency"],
        raw_path=resolve_path(data_cfg["raw_path"]),
        cache_max_age_hours=data_cfg["cache_max_age_hours"],
        refresh=refresh,
    )
    tickers = list(dict.fromkeys([*universe["tickers"], universe["benchmark"]]))
    prices = provider.get_prices(tickers, data_cfg["start"], data_cfg.get("end"))

    strategy_cfg = config["strategy"]
    strategy = strategies.get(strategy_cfg["name"])(**strategy_cfg.get("params", {}))
    strategy_label = _describe(strategy_cfg)
    benchmark = universe["benchmark"]

    runs = {
        strategy_label: _backtest(prices[universe["tickers"]], strategy, bt_cfg),
        f"Benchmark: {benchmark}": _backtest(prices[[benchmark]], BuyAndHold(benchmark), bt_cfg),
    }
    if _same(*runs.values()):  # strategy *is* the benchmark: one line, not two on top of each other
        runs = {strategy_label: runs[strategy_label]}

    periods_per_year = PERIODS_PER_YEAR[data_cfg["frequency"]]
    capital = bt_cfg["initial_capital"]
    table = {}
    for label, result in runs.items():
        row = risk.summary(
            result.returns, periods_per_year, risk_cfg["risk_free_rate"], risk_cfg["var_confidence"]
        )
        row["total_costs"] = float(result.costs.sum())
        row["final_value"] = float(result.equity(capital).iloc[-1])
        table[label] = row

    first, last = prices.index[0].date(), prices.index[-1].date()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = resolve_path(config["reporting"]["output_path"]) / f"{stamp}_{strategy_cfg['name']}"
    details = {
        "Data": f"{data_cfg['provider']}, {data_cfg['frequency']} adjusted close",
        "Period": f"{first} to {last} ({len(prices) - 1} {data_cfg['frequency']} periods)",
        "Universe": ", ".join(universe["tickers"]),
        "Benchmark": benchmark,
        "Initial capital": f"{capital:,.0f}",
        "Costs": f"{bt_cfg['commission_bps']} bp commission + {bt_cfg['slippage_bps']} bp slippage per trade",
        "Rebalance": bt_cfg["rebalance"],
        "Risk-free rate": f"{risk_cfg['risk_free_rate']:.2%} per year",
        "VaR / CVaR": f"historical, {risk_cfg['var_confidence']:.0%} confidence, one {data_cfg['frequency'][:-2]} horizon",
    }
    report = write_report(
        out_dir,
        title=f"Backtest: {strategy_label}",
        returns={label: r.returns for label, r in runs.items()},
        equity={label: r.equity(capital) for label, r in runs.items()},
        drawdowns={label: risk.drawdown(r.returns) for label, r in runs.items()},
        metrics=pd.DataFrame(table),
        details=details,
    )
    if config_path is not None:
        shutil.copy(config_path, out_dir / "config.yaml")  # exact settings behind this result
    return report


def _backtest(prices: pd.DataFrame, strategy, bt_cfg: dict) -> backtest.BacktestResult:
    prices = prices.dropna(how="all")
    return backtest.run(
        prices,
        strategy.target_weights(prices),
        commission_bps=bt_cfg["commission_bps"],
        slippage_bps=bt_cfg["slippage_bps"],
        rebalance=bt_cfg["rebalance"],
    )


def _same(a: backtest.BacktestResult, b: backtest.BacktestResult) -> bool:
    return a.returns.index.equals(b.returns.index) and np.allclose(a.returns, b.returns)


def _describe(strategy_cfg: dict) -> str:
    params = ", ".join(f"{v}" for v in strategy_cfg.get("params", {}).values())
    return f"{strategy_cfg['name']}({params})" if params else strategy_cfg["name"]
