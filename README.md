# Backtester Engine

Open-source options backtesting engine for NSE (India), built for Upstox historical data.

- Bar-by-bar simulation on 1-minute NIFTY spot + option chain data
- Strategy API modeled on `on_bar(context)` — write Python, get deterministic Parquet outputs
- Realistic cost model: STT (sell + exercised ITM), brokerage, exchange txn, GST, SEBI, stamp duty
- Local Parquet cache — every Upstox candle is fetched once, then reused across runs
- Web dashboard for metrics, equity curve, drawdown, per-trade log

## Status

v0.1 alpha. Single-leg options + spot only. Multi-leg and margin modeling in v0.2.

## License

MIT.
