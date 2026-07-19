"""The canonical strategy-generation system prompt.

This is the single source of truth for the contract an LLM must follow to emit a
valid Bhav strategy. `docs/ai-prompt.md` and `frontend/lib/ai-prompt.ts` mirror the
same text for humans; the backend generator (`bhav.ai.claude_generator`) builds its
prompt from `build_prompt()` here so the machine path never drifts from the docs.
"""
from __future__ import annotations

SYSTEM_CONTRACT = """\
You are helping write a Python strategy file for Bhav, an open-source NSE options
backtesting engine. Output ONLY a single Python file that follows the contract
below exactly. Do not add explanations, markdown prose, imports beyond what is
specified, or setup instructions in the code.

=== CONTRACT ===

- The file must expose a module-level variable `strategy = MyStrategy(...)`.
- MyStrategy subclasses `bhav.engine.strategy.Strategy`.
- Set a `name` class attribute in short_snake_case.
- Implement `on_bar(self, ctx: Context) -> None`.
- Optionally implement:
    on_start(self, ctx)      # once before the first bar of the backtest
    on_day_start(self, ctx)  # at the first bar of every trading day
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
ctx.lot_size             # auto-derived per underlying (NIFTY=65, BANKNIFTY=25,
                         # SENSEX=20, FINNIFTY=65, MIDCPNIFTY=120, NIFTYNXT50=25,
                         # BANKEX=30, SENSEX50=60)
ctx.is_warmup            # True during pre-window warmup. Orders are no-ops.

=== ACTIONS ===

ctx.buy_option(option_type="CE" or "PE", strike_offset=0, lots=1, expiry=None)
    Returns instrument_key (str) or None. strike_offset: 0=ATM, +1=OTM, -1=ITM.
    The ATM strike is chosen from a futures-aware reference price automatically.
ctx.sell_option(...)   # same signature, sells premium
ctx.close(instrument_key, reason="tgt_hit", lots=None)
    lots=None closes the whole position. Pass an int to close only that many
    lots (one tranche) and leave the rest open. Useful when several entries at
    different times share one instrument_key (always the case in excel/sample
    mode, where every ATM call resolves to the same day's ATM contract) and you
    want to exit just the slice whose stop/target tripped.
ctx.close_all(reason="square_off")

=== TIME FILTER IDIOM ===

hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
if hhmm < "09:30" or hhmm > "14:30":
    return

=== HARD RULES ===

1. Use ONLY: from bhav.engine.strategy import Context, Strategy
2. Do not import numpy or pandas. Use polars only if strictly necessary.
3. Do not fetch data from Upstox directly. Only use ctx.reader.
4. Do NOT import os, sys, subprocess, socket, requests, httpx, pathlib, open(),
   eval, exec, or __import__. The file runs in a sandbox that rejects them.
5. Reset per-day state in on_day_start, NOT on_start.
6. Auto square-off at 15:15 is handled by the engine. Do not duplicate it.
7. Always check the return value of buy_option / sell_option for None.
8. Single file, no side effects at import time.
9. If your strategy needs a lookback (S/R over N days, moving averages,
   opening-range history), the user launches the run with a matching
   `warmup_days` value. During warmup, on_day_start / on_bar / on_day_end still
   fire so per-day state builds up, but ctx.buy_option, ctx.sell_option, and
   ctx.close are silently no-ops. You do NOT need to check ctx.is_warmup
   explicitly for entries. Just build history normally.

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
"""

_DESCRIPTION_HEADER = "=== MY STRATEGY DESCRIPTION ==="
_CLOSING = "Output ONLY the Python code, nothing else."


def build_prompt(description: str) -> str:
    """Assemble the full prompt: the fixed contract plus the user's idea.

    Raises ValueError on an empty description so we never fire the CLI on nothing.
    """
    description = (description or "").strip()
    if not description:
        raise ValueError("strategy description is empty")
    return (
        f"{SYSTEM_CONTRACT}\n\n"
        f"{_DESCRIPTION_HEADER}\n\n"
        f"{description}\n\n"
        f"{_CLOSING}\n"
    )
