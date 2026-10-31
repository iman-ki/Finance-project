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
| `src/qrp/cli.py`, `pipeline.py` | Command line and the run that wires every stage together |
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
pip install -e ".[dev]"
pytest
```

Data comes from Alpha Vantage. Put your free key in `.env` (see `.env.example`):

```
ALPHAVANTAGE_API_KEY=your-key
```

## Usage

```powershell
python -m qrp run                              # uses config/default.yaml
python -m qrp run --config config/my_test.yaml # another experiment
python -m qrp run --refresh                    # force a fresh download
```

Each run prints the metrics and writes a folder under `reports/` with `report.md`, the
equity and drawdown charts, `metrics.csv`, `returns.csv` and a copy of the config used.

Data is weekly, dividend-adjusted, from late 1999 (the free key has no daily history;
see `docs/decisions/0002-alpha-vantage-weekly-data.md`).

## Roadmap

1. **Foundations:** data provider, returns, risk metrics (volatility, drawdown, Sharpe), tests. *(done in v1)*
2. **Backtest engine:** weights to P&L with costs, no look-ahead. *(done in v1)*
3. **Benchmarking and comparison:** correlation, beta/alpha, rolling metrics, VaR/CVaR.
4. **Validation:** walk-forward testing, overfitting and multiple-testing corrections.
5. **Portfolio and risk layer:** risk parity, stress tests.
6. **Fundamentals and filings:** SEC EDGAR data, LLM-assisted analysis.
7. **Advanced plugins:** factor models, stochastic models, quantum-inspired optimization.

Not financial advice. Research tooling only.
