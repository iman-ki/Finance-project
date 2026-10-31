# Architecture

## Pipeline and contracts

All stages exchange pandas DataFrames shaped **dates x tickers**.

| Stage | Contract | Input | Output |
|---|---|---|---|
| Data | `DataProvider.get_prices(tickers, start, end)` | tickers, dates | adjusted close prices |
| Signal | `Signal.compute(prices)` | prices | score per asset per date (higher = more attractive) |
| Strategy | `Strategy.target_weights(prices)` | prices | desired portfolio weights per date |
| Backtest | `run(prices, weights, costs)` | prices, weights | portfolio returns |
| Risk | metric functions | returns | numbers (volatility, drawdown, Sharpe...) |
| Reporting | report builders | returns + metrics | charts, files |

## Rules that keep results trustworthy

1. **No look-ahead.** A value on date `t` uses only data available at `t`. The backtester applies weights decided at `t` to returns from `t+1`.
2. **Costs are never zero.** Commission and slippage are configured, not ignored.
3. **Modules don't import "sideways."** Data knows nothing about strategies; strategies know nothing about the backtester internals. Dependencies flow left to right in the pipeline.
4. **Config over code.** Universe, costs and dates live in `config/`, so every experiment is reproducible.
5. **Everything numeric is tested** against small examples computed by hand.

## Adding a plugin

```python
from qrp.signals.base import Signal, signals

@signals.register("momentum_12_1")
class Momentum121(Signal):
    def compute(self, prices):
        ...
```

No core file changes. The same pattern applies to strategies and data providers.
