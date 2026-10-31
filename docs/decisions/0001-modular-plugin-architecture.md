# 0001: Modular plugin architecture

**Status:** accepted (2026-10-25)

## Context
The project is a multi-year learning vehicle. New math will keep arriving (factor models, stochastic processes, optimization), and the core must not need rewriting each time.

## Decision
Split the system into independent stages (data, signals, strategies, backtest, risk, reporting) connected by small abstract contracts, with a registry per plugin type. Python package under `src/qrp`, pandas DataFrames (dates x tickers) as the common data shape.

## Consequences
- New ideas are added as files, not edits to the core.
- Each stage is testable alone.
- Some upfront ceremony (contracts, registry) for a small codebase; accepted for long-term payoff.
- pandas is fine at daily frequency; revisit if intraday data is added.
