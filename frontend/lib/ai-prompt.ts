export const AI_PROMPT = `You are helping me write a Python strategy file for Bhav, an open-source
NSE options backtesting engine. Output ONLY a single Python file that
follows the contract below exactly. Do not add explanations, imports
beyond what is specified, or setup instructions in the code.

=== CONTRACT ===

- The file must expose a module-level variable \`strategy = MyStrategy(...)\`.
- MyStrategy subclasses \`bhav.engine.strategy.Strategy\`.
- Set a \`name\` class attribute in short_snake_case.
- Implement \`on_bar(self, ctx: Context) -> None\`.
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
ctx.reader.spot_bars(underlying_key, ctx.date)
ctx.reader.option_bars(instrument_key, ctx.date)
ctx.resolver.nearest_expiry(ctx.date)
ctx.resolver.atm_strike(spot: float) -> int
ctx.portfolio.positions  # dict, empty means flat
ctx.lot_size            # auto-derived from underlying (NIFTY=65, BANKNIFTY=25, SENSEX=20, FINNIFTY=65, MIDCPNIFTY=120, NIFTYNXT50=25, BANKEX=30, SENSEX50=60)

=== ACTIONS ===

ctx.buy_option(option_type="CE" or "PE", strike_offset=0, lots=1, expiry=None)
    Returns instrument_key (str) or None. strike_offset: 0=ATM, +1=OTM, -1=ITM.
ctx.sell_option(...)   # same signature, sells premium
ctx.close(instrument_key, reason="tgt_hit")
ctx.close_all(reason="square_off")

=== TIME FILTER IDIOM ===

hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
if hhmm < "09:30" or hhmm > "14:30":
    return

=== HARD RULES ===

1. Use ONLY: from bhav.engine.strategy import Context, Strategy
2. Do not import numpy or pandas.
3. Do not fetch data from Upstox directly. Only use ctx.reader.
4. Reset per-day state in on_day_start, NOT on_start.
5. Auto square-off at 15:15 is handled by the engine. Do not duplicate it.
6. Always check the return value of buy_option / sell_option for None.
7. Single file, no side effects at import time.

=== EXAMPLE SHAPE ===

from bhav.engine.strategy import Context, Strategy


class MyStrategy(Strategy):
    name = "my_strategy_v1"

    def __init__(self, sl_pct: float = 0.3, tgt_pct: float = 0.6):
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self._open_key = None
        self._entry = None

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
            if lo <= self._entry * (1 - self.sl_pct):
                ctx.close(self._open_key, reason="sl_hit")
                self._open_key = None
            elif hi >= self._entry * (1 + self.tgt_pct):
                ctx.close(self._open_key, reason="tgt_hit")
                self._open_key = None


strategy = MyStrategy(sl_pct=0.3, tgt_pct=0.6)

=== MY STRATEGY DESCRIPTION ===

[Describe your strategy here. Be specific about:
 - Entry trigger (time-of-day condition, price condition, indicator)
 - Which option to buy or sell (ATM/OTM/ITM, CE or PE)
 - Stop loss and target rules
 - Any special exit conditions before the auto 15:15 square-off]

Output ONLY the Python code, nothing else.`;
