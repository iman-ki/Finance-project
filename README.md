# Modular Quantitative Research Platform (QRP)

A long-term, institutional-style research platform for safely backtesting and analyzing financial strategies. Data collection, mathematical modeling, trade simulation and risk management are independent modules, so new math (signals, models, risk measures) can be added as plugins without rewriting the core.

**Purpose:** learn finance, math and physics by building. The platform grows as the knowledge does.
**Principle:** reliability over returns. A result is only worth something if the test behind it is honest.

## Architecture

```
data  ->  signals  ->  strategies  ->  backtest  ->  risk  ->  reporting
(prices)  (scores)    (weights)       (simulated     (metrics)  (charts,
                                       P&L + costs)             reports)
```

Each stage only talks to the next through a small contract (see `docs/architecture.md`). A new idea is one new file plus a registry decorator.

## Layout

| Path | Purpose |
|---|---|
| `src/qrp/core/` | Plugin registry, config loading |
| `src/qrp/data/` | Data providers and storage (contract: `DataProvider`) |
| `src/qrp/signals/` | Math plugins that score assets (contract: `Signal`) |
| `src/qrp/strategies/` | Turn signals into target weights (contract: `Strategy`) |
| `src/qrp/backtest/` | Simulation engine and cost models |
| `src/qrp/risk/` | Volatility, drawdown, Sharpe, VaR/CVaR, beta |
| `src/qrp/portfolio/` | Weighting schemes and constraints |
| `src/qrp/reporting/` | Charts and performance reports |
| `config/` | YAML settings; experiments change config, not code |
| `data/` | Local data (git-ignored): `raw/`, `processed/`, `cache/` |
| `notebooks/` | Learning and exploration |
| `docs/` | Architecture, decisions, learning log |
| `tests/` | Every metric checked against hand-computed examples |

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,data]"
pytest
```

## Roadmap

1. **Foundations:** data provider, returns, risk metrics (volatility, drawdown, Sharpe), tests.
2. **Backtest engine:** weights to P&L with costs, no look-ahead.
3. **Benchmarking and comparison:** correlation, beta/alpha, rolling metrics, VaR/CVaR.
4. **Validation:** walk-forward testing, overfitting and multiple-testing corrections.
5. **Portfolio and risk layer:** risk parity, stress tests.
6. **Fundamentals and filings:** SEC EDGAR data, LLM-assisted analysis.
7. **Advanced plugins:** factor models, stochastic models, quantum-inspired optimization.

Not financial advice. Research tooling only.
