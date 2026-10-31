# 0002: Alpha Vantage, weekly adjusted prices, full history

**Status:** accepted (2026-10-31)

## Context
Alpha Vantage replaces yfinance as the data source. Its free key was tested on 2026-10-31:

| Endpoint | Free key result |
|---|---|
| `TIME_SERIES_DAILY_ADJUSTED` | premium only |
| `TIME_SERIES_DAILY`, `outputsize=full` | premium only |
| `TIME_SERIES_DAILY`, compact | last 100 days, **not** dividend-adjusted |
| `TIME_SERIES_WEEKLY_ADJUSTED` | 1999-11-12 to today, dividend- and split-adjusted |
| `TIME_SERIES_MONTHLY_ADJUSTED` | 1999-12-31 to today, adjusted |

Limits: 25 requests per day, 1 request per second.

## Decision
- Use **weekly adjusted close** by default (monthly is also supported). Daily raises an error explaining it needs a premium key.
- Fetch **the full history** (late 1999 onward). It costs one request per ticker regardless of length, and the saved response for SPY is 280 KB (about 2 MB for all 8 planned tickers). A short window would save nothing and would leave out the 2000-02 and 2008-09 crashes, which are exactly what drawdown and VaR need to see.
- Save each raw response under `data/raw/alphavantage/` and reuse it for 24 hours, so reruns cost no requests and every result can be re-derived offline. If a download fails and a saved copy exists, use it with a warning.
- Annualize with the data frequency (52 for weekly) rather than a fixed 252.

## Consequences
- 1,400 weekly points instead of about 6,800 daily ones. Fine for allocation strategies rebalanced monthly; too coarse for anything that trades within a week.
- Weekly VaR/CVaR is a one-week loss, not one-day.
- The adjusted close includes dividends: SPY's 1999-2026 CAGR is 8.3% with them and 6.5% price-only.
- The last weekly bar may be a partial week if run mid-week.
- Survivorship bias still applies to any stock universe; it does not affect SPY.
- Revisit if a premium key or a second provider (e.g. Tiingo) is added: the contract does not change, only the provider.
