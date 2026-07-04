# Bhav

*Hindi/Marathi/Gujarati word for "market rate" — what every Indian trader means when they say "aaj ka bhav kya hai?"*

Open-source options backtesting engine for NSE (India), built for Upstox historical data.

- Bar-by-bar simulation on 1-minute NIFTY spot + option chain data
- Strategy API modeled on `on_bar(context)` — write Python, get deterministic Parquet outputs
- Realistic cost model: STT (sell + exercised ITM), brokerage, exchange txn, GST, SEBI, stamp duty
- Local Parquet cache — every Upstox candle is fetched once, then reused across runs
- Web dashboard for metrics, equity curve, drawdown, per-trade log

## Status

v0.1 alpha. Single-leg options + spot only. Multi-leg and margin modeling in v0.2.

## Write your own strategy

A strategy is one Python file that exposes a `strategy` variable. Minimum viable example:

```python
from bhav.engine.strategy import Context, Strategy

class BuyATMCallAtOpen(Strategy):
    name = "buy_atm_call_at_open"

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if hhmm == "09:30" and not ctx.portfolio.positions:
            ctx.buy_option(option_type="CE", strike_offset=0, lots=1)

strategy = BuyATMCallAtOpen()
```

Then:

```powershell
$env:UPSTOX_TOKEN = "your_token"
bhav run my_strategy.py --start 2025-08-01 --end 2025-11-30
```

Full guide with API reference, three worked examples, common patterns, and common mistakes: [docs/writing-strategies.md](docs/writing-strategies.md).

Reference strategy: [examples/orb_v1.py](examples/orb_v1.py).

## License

MIT.
