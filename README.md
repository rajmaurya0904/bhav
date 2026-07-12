# Bhav

*Hindi/Marathi/Gujarati word for "market rate" — what every Indian trader means when they say "aaj ka bhav kya hai?"*

Open-source options backtesting engine for NSE (India), built specifically around Upstox's historical-data endpoints. Write a strategy in Python, run it against real 1-minute spot + option data, get a deterministic Parquet result and a full metrics dashboard.

- Bar-by-bar simulation on 1-minute NIFTY/BANKNIFTY/SENSEX (and other index) spot + option chain data
- Strategy API modeled on lifecycle hooks (`on_bar`, `on_day_start`, `on_day_end`, ...) — write plain Python, get deterministic Parquet output
- Pulls expired option contracts directly from Upstox's `expired-instruments` endpoints, so you can backtest premiums for contracts that expired months or years ago, not just currently-listed ones
- Realistic Indian cost model: STT (sell + exercised ITM), brokerage, exchange txn charge, SEBI charges, stamp duty, GST
- Engine-level `warmup_days` so lookback strategies (rolling S/R, moving averages) get correct history from day one of the window
- Local Parquet cache — every Upstox candle is fetched once, then reused across runs
- Per-underlying lot size / ATM-step table (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, NIFTYNXT50, SENSEX, BANKEX, SENSEX50) with auto-lookup
- FastAPI backend + Next.js frontend: upload a strategy file, set token/dates/capital, run a real backtest, see equity curve, drawdown, P&L distribution, and full trade log

## Status

v0.1 alpha. Single-leg options + spot only, Upstox-only. Multi-leg and margin modeling in v0.2. More brokers (Zerodha Kite, Angel One, Fyers, ...) are on the roadmap — the data layer (`bhav/data/upstox_client.py`) is written as a single swappable client so adding another broker means implementing the same 4-endpoint interface, not touching the engine.

## Requirements

- Python 3.11+
- An Upstox Pro account with historical data API access, and an access token (expires daily around 03:30 IST — generate a fresh one each session)
- Node.js 20+ (only needed for the frontend)

## Install

One command (clones the repo, installs the Python package, installs frontend deps):

```powershell
npx @rajmaurya0904/create-bhav
```

Or manually:

```powershell
git clone https://github.com/rajmaurya0904/bhav.git
cd bhav

# backend
pip install -e .

# frontend (optional, only if you want the web UI)
cd frontend
npm install
```

## Quickstart — CLI

```powershell
$env:UPSTOX_TOKEN = "your_token"
bhav run examples/orb_v1.py --start 2025-08-01 --end 2025-11-30
```

Useful flags:

```
--underlying "NSE_INDEX|Nifty 50"   # default; see lot-size table below for others
--capital 500000                    # starting capital, default 500000
--lot-size 0                        # 0 = auto-lookup per underlying, or set explicitly
--warmup-days 3                     # pre-window replay so lookback strategies have history from day 1
```

Results are written to `runs/<run_id>/` as `trades.parquet`, `equity_curve.parquet`, `metrics.json`, and `manifest.json` (with a SHA256 checksum of the metrics for reproducibility).

## Quickstart — Web UI

```powershell
# terminal 1: API server
bhav-server

# terminal 2: frontend
cd frontend
npm run dev
```

Open `http://localhost:3000`. Go to `/new`, upload a strategy `.py` file, paste your Upstox token, set dates/underlying/capital/lot size/warmup days, and run. The results page polls until the run completes and shows total return, CAGR, Sharpe/Sortino, max drawdown, win rate, profit factor, expectancy, an equity curve, a drawdown curve, a P&L distribution, and the full trade log.

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

Full guide with API reference, worked examples, common patterns, and common mistakes (including the broker-candle-order gotcha): [docs/writing-strategies.md](docs/writing-strategies.md).

Don't want to write the Python yourself? [docs/ai-prompt.md](docs/ai-prompt.md) has a copy-pasteable prompt block that gets ChatGPT/Claude/Gemini to generate a strategy following Bhav's contract — the `/new` page in the frontend has the same prompt with a one-click copy button.

### Reference strategies

All in [examples/](examples/), runnable as-is:

| File | Idea |
|---|---|
| [orb_v1.py](examples/orb_v1.py) | Opening-range breakout/fade on ATM options, SL/target/trailing-SL ladder, hard time exit |
| [morning_3min_momentum.py](examples/morning_3min_momentum.py) | First two 3-min candles at open; second candle's color picks CE/PE |
| [morning_momentum.py](examples/morning_momentum.py) | Point-move threshold from day open by 09:30 |
| [straddle_sell_920.py](examples/straddle_sell_920.py) | Short straddle sold shortly after open |
| [spike_fade.py](examples/spike_fade.py) | Fade a fast spot spike |

## Lot sizes (Jan 2026 revision)

| Underlying | Lot size | ATM step |
|---|---|---|
| NIFTY 50 | 65 | 50 |
| BANK NIFTY | 25 | 100 |
| FIN NIFTY | 65 | 50 |
| MIDCAP NIFTY | 120 | 25 |
| NIFTY NEXT 50 | 25 | 100 |
| SENSEX | 20 | 100 |
| BANKEX | 30 | 100 |
| SENSEX 50 | 60 | 100 |

Pass `--lot-size 0` (CLI) or leave lot size on auto (UI) to use this table automatically per underlying.

## How it works

1. `bhav.data.upstox_client.UpstoxClient` wraps Upstox's 4 relevant endpoints: `historical-candle` (spot), `expired-instruments/expiries`, `expired-instruments/option/contract`, `expired-instruments/historical-candle` (expired option premiums).
2. `bhav.data.cache.ParquetCache` caches every candle series to `~/.bhav/cache`, keyed by instrument + interval + date, always sorted ascending by timestamp.
3. `bhav.engine.bar_engine.BarEngine` replays 1-minute bars in order, calling your strategy's lifecycle hooks, optionally preceded by `warmup_days` of no-op replay so lookback state is built before live trading starts.
4. `bhav.engine.portfolio.Portfolio` tracks positions and realized trades, applying `bhav.engine.costs.IndianCostModel` on every fill.
5. `bhav.metrics.report` computes CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor, and expectancy from the equity curve and trade log.
6. `bhav.output.writer.ResultWriter` writes everything to `runs/<run_id>/` as Parquet + JSON with a manifest and checksum.

## License

MIT.
