# Modular Quantitative Research Platform (QRP)

This project is a long-term, research program for safely backtesting and analyzing financial strategies. Data collection, mathematical modeling, trade simulation and risk management are independent modules, so new math (signals, models, risk measures) can be added as plugins without rewriting the core.

**Purpose:** Help the user test strategies while learning finance and math. The platform grows as the knowledge does.
**Principle:** reliability over returns. Human leads the build, Claude helps speed the build. A result is only worth something if the user understands the reason of that result and if the test behind it is honest.

## Architecture

```
1. data  ->  2. strategy creation  ->  3. risk management  ->  4. simulation  ->  5. evals
(prices)     (target weights)          (allowed weights)        (returns after    (metrics,
                                                                  costs)            reports, app)
```

Each stage only talks to the next through a small contract (see `docs/architecture.md`). A new idea is one new file plus a registry decorator.

## Layout

| Path | Stage | Purpose |
|---|---|---|
| `src/qrp/data/` | 1 | Data providers and storage (contract: `DataProvider`) |
| `src/qrp/strategies/` | 2 | Strategies that turn prices into target weights (contract: `Strategy`) |
| `src/qrp/strategies/signals/` | 2 | Math building blocks that score assets (contract: `Signal`) |
| `src/qrp/risk/` | 3 | Risk models that review and limit weights before trading (contract: `RiskModel`) |
| `src/qrp/backtest/` | 4 | Simulation engine: costs, drift, no look-ahead |
| `src/qrp/evals/` | 5 | Metrics (CAGR, volatility, Sharpe, drawdown, VaR/CVaR) and reports |
| `src/qrp/pipeline.py` | 1-5 | Runs the stages in order from a config |
| `src/qrp/cli.py`, `app.py` | | Command line and interactive app, both over the pipeline |
| `src/qrp/core/` | | Plugin registry, config loading |
| `config/` | | YAML settings, one section per stage; experiments change config, not code |
| `data/` | | Local data (git-ignored): `raw/`, `processed/`, `cache/` |
| `notebooks/` | | Learning and exploration |
| `docs/` | | Architecture, decisions, learning log |
| `tests/` | | Every number checked against hand-computed examples |

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

At the minute data comes from Yahoo Finance via `yfinance`. 
Then I'll use Alpha Vantage API key. If you want to do it set `data.provider: alphavantage` (and `frequency: weekly`) in the config and put your key in `.env` (see `.env.example`). Adding another provider is one file in `src/qrp/data/providers/`.
At the moment it runs local, but the idea is to run it on a VPC with the Alpha Vantage API Key for autmatic data collection.

## Usage

```powershell
python -m qrp run                              # uses config/default.yaml
python -m qrp run --config config/my_test.yaml # another experiment
python -m qrp run --refresh                    # force a fresh download
python -m qrp app                              # interactive app in the browser
```

The app (`src/qrp/app.py`, Streamlit) has three tabs: **Backtest** (pick tickers, strategy,
costs and dates; interactive charts and metrics vs the benchmark; save the run as a report),
**Data** (growth of 100, per-ticker stats, correlations) and **Project map** (the pipeline,
which parts exist and which are planned, the roadmap). New strategies appear in it
automatically, with one input per constructor argument.

Each run prints the metrics and writes a folder under `reports/` with `report.md`, the
equity and drawdown charts, `metrics.csv`, `returns.csv` and a copy of the config used.

Data is daily and split/dividend-adjusted, from 1993 for SPY (see
`docs/decisions/0003-yfinance-as-default-provider.md`). Downloads are saved in `data/raw/`
and reused for 24 hours.

## Roadmap

1. **Foundations:** data provider, returns, risk metrics (volatility, drawdown, Sharpe), tests. *(done in v1)*
2. **Backtest engine:** weights to P&L with costs, no look-ahead. *(done in v1)*
3. **Benchmarking and comparison:** correlation, beta/alpha, rolling metrics, VaR/CVaR.
4. **Validation:** walk-forward testing, overfitting and multiple-testing corrections.
5. **Portfolio and risk layer:** risk parity, stress tests.
6. **Fundamentals and filings:** SEC EDGAR data, LLM-assisted analysis.
7. **Advanced plugins:** factor models, stochastic models, quantum-inspired optimization.

Not financial advice. Research and learning tooling only.
