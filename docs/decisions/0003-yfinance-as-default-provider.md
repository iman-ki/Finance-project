# 0003: yfinance as the default data provider (temporary)

**Status:** accepted (2026-10-31). Supersedes the default in [0002](0002-alpha-vantage-weekly-data.md); the Alpha Vantage provider stays available.

## Context
Alpha Vantage's free key gives only weekly or monthly history (daily is premium), which is too coarse for strategies that need daily data. yfinance is free, needs no key and has daily history back to 1993 for SPY. It is unofficial and can break without notice; the plan is to replace it with a better API when one is available.

## Decision
- `data.provider: yfinance` and `data.frequency: daily` are the defaults. `alphavantage` remains selectable (weekly or monthly only).
- Prices are split- and dividend-adjusted closes (`auto_adjust=True`). Each ticker's history is requested from 1980 and starts when Yahoo's data starts. SPY: 1993-01-29, 8,497 daily rows, 125 KB.
- Each download is saved under `data/raw/yfinance/` and reused for 24 hours (same rule as Alpha Vantage), so reruns are offline, results are reproducible and a Yahoo outage does not stop a run if a saved copy exists.
- Tickers are downloaded one at a time. yfinance's parallel mode failed with `database is locked` in testing, and its timezone cache is moved into `data/cache/`.
- Annualization follows the frequency: 252 for daily, 52 for weekly, 12 for monthly.

## Consequences
- Daily VaR/CVaR and a 1993 start (adds the 1994 bond selloff and the 1997-98 crises to the sample).
- Known yfinance weaknesses: survivorship bias for stock universes (delisted companies are missing), occasional adjustment errors, and no guarantee the API keeps working. Treat results as research, not as proof.
- A new provider is one file in `data/providers/` plus a config change; the rest of the system does not change. Sanity check when switching: the last close should match across providers (SPY 755.72 on 2026-10-30 matched between Yahoo and Alpha Vantage).
