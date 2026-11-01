# 0004: Five-stage architecture

**Status:** accepted (2026-11-01). Refines [0001](0001-modular-plugin-architecture.md).

## Context
The original pipeline was data -> signals -> strategies -> backtest -> risk -> reporting, where
"risk" meant metrics computed after the backtest. Two things were missing: a place to enforce
risk rules *before* trading (the long-only, no-leverage assumptions were implicit), and a clear
name for judging results.

## Decision
Organize the platform as five stages, in order:

1. **Data** (`data/`), unchanged.
2. **Strategy creation** (`strategies/`). Signals move to `strategies/signals/`: they are building blocks of strategies, not a stage of their own.
3. **Risk management** (`risk/`, new contract `RiskModel`). Reviews target weights before trading. First model: `limits` (long-only, max weight per asset, max gross exposure). The empty `portfolio/` package is folded in here.
4. **Simulation / backtesting** (`backtest/`), unchanged.
5. **Evals** (`evals/`). The former `risk/metrics.py` and `reporting/` together: metrics, reports, charts.

Config gets one section per stage (`risk_management` and `evals` replace `risk` and `reporting`).

## Consequences
- The core math is unchanged and so are results: the default limits (long-only, 100% max weight, 100% gross) match what v1 assumed. SPY buy-and-hold gives the same numbers before and after.
- Risk rules are now explicit, configurable and tested, and every run reports how often they changed the strategy's weights.
- New risk ideas (volatility targeting, risk parity, stress limits) have an obvious home.
- Older saved reports keep their old config layout; they are records, not inputs.
