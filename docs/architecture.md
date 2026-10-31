# Architecture

## Pipeline and contracts

All stages exchange pandas DataFrames shaped **dates x tickers**. One row is one period
of the configured frequency (weekly by default, see decision 0002).

| Stage | Contract | Input | Output | v1 implementation |
|---|---|---|---|---|
| Data | `DataProvider.get_prices(tickers, start, end)` | tickers, dates | adjusted close prices | `data/providers/alphavantage.py` |
| Signal | `Signal.compute(prices)` | prices | score per asset per date (higher = more attractive) | none yet |
| Strategy | `Strategy.target_weights(prices)` | prices | desired portfolio weights per date | `strategies/buy_and_hold.py` |
| Backtest | `backtest.run(prices, weights, commission_bps, slippage_bps, rebalance)` | prices, weights | `BacktestResult` (returns, costs, turnover, held weights) | `backtest/engine.py` |
| Risk | metric functions | returns | numbers (CAGR, volatility, drawdown, Sharpe, VaR/CVaR) | `risk/metrics.py` |
| Reporting | `write_report(...)` | returns + metrics | charts, CSVs, `report.md` | `reporting/report.py` |

`qrp/pipeline.py` wires the stages together from a config file; `qrp/cli.py` exposes it as
`python -m qrp run`.

## Rules that keep results trustworthy

1. **No look-ahead.** A value on date `t` uses only data available at `t`. The backtester applies weights decided at `t` to returns from `t+1`.
2. **Costs are never zero.** Commission and slippage are configured, not ignored. Cost = turnover x (commission + slippage).
3. **Holdings drift.** Between rebalance dates, positions move with prices; the engine does not silently rebalance every period.
4. **Modules don't import "sideways."** Data knows nothing about strategies; strategies know nothing about the backtester internals. Dependencies flow left to right in the pipeline. Only `pipeline.py` sees all stages.
5. **Config over code.** Universe, costs, dates and strategy live in `config/`, so every experiment is reproducible. Each report folder keeps a copy of the config that produced it.
6. **Raw data is kept.** API responses are saved untouched in `data/raw/`, so results can be re-derived offline.
7. **Everything numeric is tested** against small examples computed by hand.

## Adding a plugin

```python
# src/qrp/strategies/my_idea.py
from qrp.strategies.base import Strategy, strategies

@strategies.register("my_idea")
class MyIdea(Strategy):
    def __init__(self, lookback: int = 12): ...
    def target_weights(self, prices): ...
```

Then select it in the config:

```yaml
strategy:
  name: my_idea
  params: {lookback: 12}
```

No core file changes: every module in `strategies/` and `data/providers/` is imported
automatically. The same pattern applies to signals and data providers.
