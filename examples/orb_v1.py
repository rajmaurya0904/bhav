"""ORB v1 reference strategy, faithfully ported from nifty_orb_v1.py.

Matches the standalone script's semantics exactly:
    - Opening range 09:15-09:29 (spot high/low)
    - Exactly ONE trade per day: first 1-min close outside the range,
      watched only until `session_end`. No re-entry after a stop-out.
    - SL / target on option premium, SL checked first if both touch
      the same bar (conservative).
    - Trailing-SL ladder: as premium runs in favor, the stop is moved
      up in steps (never backwards).
    - Hard time-based exit at `eod_squareoff`, independent of the
      engine's own auto square-off (which defaults to 15:15). This is
      the knob the original script calls EOD_SQUAREOFF.

Run:
    UPSTOX_TOKEN=... bhav run examples/orb_v1.py --start 2025-08-01 --end 2026-05-30
"""
from __future__ import annotations

from bhav.engine.strategy import Context, Strategy


class OpeningRangeBreakout(Strategy):
    name = "orb_v1"

    def __init__(
        self,
        mode: str = "FADE",
        sl_pct: float = 0.30,
        tgt_pct: float = 0.60,
        session_end: str = "12:00",       # stop watching for NEW breakouts after this
        eod_squareoff: str = "12:00",     # force-exit an OPEN trade at this time
        trail_ladder: tuple[tuple[float, float], ...] = (
            (0.20, 0.00),
            (0.40, 0.20),
            (0.50, 0.35),
        ),
    ) -> None:
        self.mode = mode
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.session_end = session_end
        self.eod_squareoff = eod_squareoff
        self.trail_ladder = trail_ladder

        self._orh: float | None = None
        self._orl: float | None = None
        self._traded_today = False  # one trade per day, no re-entry after stop-out
        self._in_trade = False
        self._entry_price: float | None = None
        self._open_key: str | None = None
        self._sl_level: float | None = None
        self._tgt_level: float | None = None
        self._ladder: list[tuple[float, float]] = []
        self._trail_steps_done = 0

    def on_day_start(self, ctx: Context) -> None:
        self._orh = None
        self._orl = None
        self._traded_today = False
        self._reset_position()

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        if "09:15" <= hhmm < "09:30":
            self._orh = ctx.bar.high if self._orh is None else max(self._orh, ctx.bar.high)
            self._orl = ctx.bar.low if self._orl is None else min(self._orl, ctx.bar.low)
            return
        if self._orh is None or self._orl is None:
            return

        if self._in_trade:
            self._manage(ctx, hhmm)
            return

        # One trade per day: never look for a new entry after the first is taken,
        # even if it already stopped out.
        if self._traded_today:
            return
        if hhmm >= self.session_end:
            return

        close = ctx.bar.close
        signal: str | None = None
        if close > self._orh:
            signal = "CE" if self.mode == "BREAKOUT" else "PE"
        elif close < self._orl:
            signal = "PE" if self.mode == "BREAKOUT" else "CE"
        if signal:
            key = ctx.buy_option(option_type=signal, strike_offset=0, lots=1)
            if key:
                entry = ctx.portfolio.positions[key].avg_price
                self._in_trade = True
                self._traded_today = True
                self._open_key = key
                self._entry_price = entry
                self._sl_level = entry * (1 - self.sl_pct)
                self._tgt_level = entry * (1 + self.tgt_pct)
                self._ladder = [
                    (entry * (1 + trg), entry * (1 + new)) for trg, new in self.trail_ladder
                ]
                self._trail_steps_done = 0

    def _manage(self, ctx: Context, hhmm: str) -> None:
        if not self._entry_price or not self._open_key or self._sl_level is None:
            return
        if self._open_key not in ctx.portfolio.positions:
            self._reset_position()
            return
        bars = ctx.reader.option_bars(self._open_key, ctx.date)
        row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
        if row.is_empty():
            return
        hi = float(row["high"][0])
        lo = float(row["low"][0])

        # SL checked first: if both SL and target touch the same bar, SL wins.
        if lo <= self._sl_level:
            reason = "trail_sl" if self._trail_steps_done > 0 else "sl_hit"
            ctx.close(self._open_key, reason=reason)
            self._reset_position()
            return

        if hi >= self._tgt_level:
            ctx.close(self._open_key, reason="tgt_hit")
            self._reset_position()
            return

        # Advance the trailing-SL ladder using the bar high. SL never moves backwards.
        while self._trail_steps_done < len(self._ladder) and hi >= self._ladder[self._trail_steps_done][0]:
            new_sl = self._ladder[self._trail_steps_done][1]
            if new_sl > self._sl_level:
                self._sl_level = new_sl
            self._trail_steps_done += 1

        # Hard time-based exit, independent of the engine's global auto square-off.
        if hhmm >= self.eod_squareoff:
            ctx.close(self._open_key, reason="time_exit")
            self._reset_position()

    def _reset_position(self) -> None:
        self._in_trade = False
        self._entry_price = None
        self._open_key = None
        self._sl_level = None
        self._tgt_level = None
        self._ladder = []
        self._trail_steps_done = 0


strategy = OpeningRangeBreakout(mode="BREAKOUT")
