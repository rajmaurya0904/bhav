# Generate a Bhav Strategy with AI

Paste the prompt below into ChatGPT, Claude, Gemini, or any capable LLM. Replace the placeholder at the bottom with a plain-English description of your strategy. The model will return a single Python file you can save and run with `bhav run my_strategy.py`.

The frontend `/new` page shows the same prompt with a one-click copy button.

---

## The prompt

```text
You are helping me write a Python strategy file for Bhav, an open-source
NSE options backtesting engine. Output ONLY a single Python file that
follows the contract below exactly. Do not add explanations, imports
beyond what is specified, or setup instructions in the code.

=== CONTRACT ===

- The file must expose a module-level variable `strategy = MyStrategy(...)`.
- MyStrategy subclasses `bhav.engine.strategy.Strategy`.
- Set a `name` class attribute in short_snake_case.
- Implement `on_bar(self, ctx: Context) -> None`.
- Optionally implement:
    on_start(self, ctx)      # once before the first bar of the backtest
    on_day_start(self, ctx)  # at 09:15 every trading day
    on_day_end(self, ctx)    # after the last bar of every day
    on_end(self, ctx)        # once after the backtest completes

=== CONTEXT API ===

ctx.date              # datetime.date, current trading day
ctx.bar               # current 1-minute bar of the underlying
ctx.bar.timestamp     # tz-aware Asia/Kolkata
ctx.bar.open/high/low/close/volume/oi
ctx.spot()            # shortcut for ctx.bar.close
ctx.reader.spot_bars(underlying_key, ctx.date)      # polars DataFrame
ctx.reader.option_bars(instrument_key, ctx.date)    # polars DataFrame
ctx.resolver.nearest_expiry(ctx.date)               # date
ctx.resolver.atm_strike(spot: float) -> int
ctx.portfolio.positions  # dict of open positions, empty means flat
ctx.lot_size             # auto-derived per underlying:
                         # NIFTY=65, BANKNIFTY=25, SENSEX=20, FINNIFTY=65,
                         # MIDCPNIFTY=120, NIFTYNXT50=25, BANKEX=30, SENSEX50=60

=== ACTIONS ===

ctx.buy_option(option_type="CE" or "PE", strike_offset=0, lots=1, expiry=None)
    Returns instrument_key (str) or None if the option could not be resolved.
    strike_offset: 0 = ATM, +1 = one strike OTM, -1 = one strike ITM.

ctx.sell_option(...)   # same signature, sells premium
ctx.close(instrument_key, reason="tgt_hit")
ctx.close_all(reason="square_off")

=== TIME FILTER IDIOM ===

hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
if hhmm < "09:30" or hhmm > "14:30":
    return

=== HARD RULES ===

1. Use ONLY: `from bhav.engine.strategy import Context, Strategy`
2. Do not import numpy or pandas. Use polars only if strictly necessary.
3. Do not fetch data from Upstox directly. Only use ctx.reader.
4. Reset per-day state in on_day_start, NOT on_start.
5. Auto square-off at 15:15 is handled by the engine automatically. Do not
   duplicate it in your code.
6. Always check the return value of buy_option / sell_option for None before
   using the key.
7. Keep it a single file with no external side effects at import time.

=== EXAMPLE OUTPUT SHAPE ===

from bhav.engine.strategy import Context, Strategy


class MyStrategy(Strategy):
    name = "my_strategy_v1"

    def __init__(self, sl_pct: float = 0.3, tgt_pct: float = 0.6):
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self._open_key: str | None = None
        self._entry: float | None = None

    def on_day_start(self, ctx: Context) -> None:
        self._open_key = None
        self._entry = None

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if self._open_key is None and hhmm == "09:30":
            key = ctx.buy_option(option_type="CE", strike_offset=0, lots=1)
            if key:
                self._open_key = key
                self._entry = ctx.portfolio.positions[key].avg_price
            return

        if self._open_key and self._entry:
            bars = ctx.reader.option_bars(self._open_key, ctx.date)
            row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
            if row.is_empty():
                return
            hi, lo = float(row["high"][0]), float(row["low"][0])
            sl = self._entry * (1 - self.sl_pct)
            tgt = self._entry * (1 + self.tgt_pct)
            if lo <= sl:
                ctx.close(self._open_key, reason="sl_hit")
                self._open_key = None
            elif hi >= tgt:
                ctx.close(self._open_key, reason="tgt_hit")
                self._open_key = None


strategy = MyStrategy(sl_pct=0.3, tgt_pct=0.6)

=== MY STRATEGY DESCRIPTION ===

[Describe your strategy here. Be specific about:
 - Entry trigger (time-of-day condition, price condition, indicator)
 - Which option to buy or sell (ATM/OTM/ITM, CE or PE)
 - Stop loss and target rules
 - Any special exit conditions before the auto 15:15 square-off]

Output ONLY the Python code, nothing else.
```

## How to use it

1. Copy the block above.
2. Paste into your AI chat.
3. Replace the last section with your idea. Be specific — the more precise you are about entry/exit, the better the code.
4. Save the returned code as `my_strategy.py`.
5. Run:

    ```powershell
    $env:UPSTOX_TOKEN = "your_token"
    bhav run my_strategy.py --start 2025-08-01 --end 2025-11-30
    ```

Or upload the file on the `/new` page in the frontend.

## Tips for good AI-generated strategies

- **Say the timeframe.** "1-min bars, ride the trade until 15:15" is clearer than "intraday".
- **Give a concrete rule.** "Buy ATM CE when the 09:30 bar closes above the 09:15-09:29 opening range high" beats "buy on breakouts".
- **Name the stop.** "30% stop on premium" is unambiguous. "Tight stop" is not.
- **Ask for a paper trail.** Tell the model to add short comments explaining any non-obvious block.
- **Read the output before running it.** AI code is fast to write and easy to trust. Do not trust it blindly with your money — the whole point of a backtester is that you can check.
