# Architecture

## Pipeline and contracts

```
1. data  ->  2. strategy creation  ->  3. risk management  ->  4. simulation  ->  5. evals
```

All stages exchange pandas DataFrames shaped **dates x tickers**. One row is one period of
the configured frequency (daily by default, see decisions 0002 and 0003).

| # | Stage | Package | Contract | Input | Output | Implemented |
|---|---|---|---|---|---|---|
| 1 | Data | `data/` | `DataProvider.get_prices(tickers, start, end)` | tickers, dates | adjusted close prices | `yfinance` (default), `alphavantage` |
| 2 | Strategy creation | `strategies/` | `Strategy.target_weights(prices)` | prices | the weights the strategy wants | `buy_and_hold` |
| | (building blocks) | `strategies/signals/` | `Signal.compute(prices)` | prices | score per asset per date | none yet |
| 3 | Risk management | `risk/` | `RiskModel.apply(weights, prices)` | target weights, prices | the weights allowed to trade | `limits` |
| 4 | Simulation | `backtest/` | `backtest.run(prices, weights, commission_bps, slippage_bps, rebalance)` | prices, allowed weights | `BacktestResult` (returns, costs, turnover, held weights) | engine |
| 5 | Evals | `evals/` | metric functions, `write_report(...)` | returns | CAGR, volatility, Sharpe, drawdown, VaR/CVaR; charts, CSVs, `report.md` | `metrics.py`, `report.py` |

`qrp/pipeline.py` runs the stages in this order from a config file (`simulate` keeps the
results in memory, `save_report` writes them). Two front ends sit on top of it and compute
nothing themselves: `qrp/cli.py` (`python -m qrp run`) and `qrp/app.py` (`python -m qrp app`).

### Risk management vs evals

Both deal with risk, at different moments:

- **Stage 3, risk management** acts *before* trading. It can only cut, cap or scale the
  strategy's positions (no shorts, at most X% in one asset, no leverage...). Each run records
  on how many dates it changed something, so a strategy that keeps hitting its limits is visible.
- **Stage 5, evals** measures *after* trading: how much risk the run actually took
  (volatility, drawdown, VaR) and whether it was paid for it (CAGR, Sharpe).

The benchmark is a reference, so it skips stage 3 and is simulated as-is.

## Rules that keep results trustworthy

1. **No look-ahead.** A value on date `t` uses only data available at `t`. The simulation applies weights decided at `t` to returns from `t+1`.
2. **Risk management before trading.** No weight reaches the simulation without passing the configured limits.
3. **Costs are never zero.** Commission and slippage are configured, not ignored. Cost = turnover x (commission + slippage).
4. **Holdings drift.** Between rebalance dates, positions move with prices; the engine does not silently rebalance every period.
5. **Modules don't import "sideways."** Each stage knows only its own contract. Dependencies flow left to right; only `pipeline.py` sees every stage.
6. **Config over code.** One config section per stage, so every experiment is reproducible. Each report folder keeps a copy of the config that produced it.
7. **Same period for everyone.** A run starts on the first date every ticker (universe and benchmark) has a price, so nothing sits in cash waiting for a younger asset and the comparison is fair.
8. **Raw data is kept.** API responses are saved untouched in `data/raw/`, so results can be re-derived offline.
9. **Everything numeric is tested** against small examples computed by hand.

## Adding a plugin

Every plugin type works the same way: a new file with a registry decorator, then a config change.

```python
# src/qrp/strategies/my_idea.py          (stage 2)
from qrp.strategies.base import Strategy, strategies

@strategies.register("my_idea")
class MyIdea(Strategy):
    def __init__(self, lookback: int = 12): ...
    def target_weights(self, prices): ...
```

```python
# src/qrp/risk/vol_target.py             (stage 3)
from qrp.risk.base import RiskModel, risk_models

@risk_models.register("vol_target")
class VolTarget(RiskModel):
    def __init__(self, target: float = 0.10): ...
    def apply(self, weights, prices): ...
```

```yaml
strategy:
  name: my_idea
  params: {lookback: 12}
risk_management:
  model: vol_target
  params: {target: 0.10}
```

No core file changes: every module in `data/providers/`, `strategies/`, `strategies/signals/`
and `risk/` is imported automatically, and the app builds one input per constructor argument.
