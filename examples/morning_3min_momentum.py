"""Morning 3-min momentum capture.

Builds two 3-minute candles from the spot 1-min bars right at market open:
    Candle 1: 09:15-09:17  (period 09:15-09:18)
    Candle 2: 09:18-09:20  (period 09:18-09:21)

The instant candle 2 completes (its 09:20 close), check its color:
    - Green (close > open) -> buy ATM PE  (fade)
    - Red   (close < open) -> buy ATM CE  (fade)
    - Flat  (close == open) -> no trade

SL / target on option premium, with a trailing-SL ladder that locks in
profit as the trade runs. One trade per day, no re-entry after exit.
Auto square-off at 15:15 is handled by the engine.

Run:
    UPSTOX_TOKEN=... bhav run examples/morning_3min_momentum.py --start 2025-08-01 --end 2025-08-31
"""
from __future__ import annotations

from bhav.engine.strategy import Context, Strategy


class Morning3MinMomentum(Strategy):
    name = "morning_3min_momentum"

    def __init__(
        self,
        sl_pct: float = 0.30,
        tgt_pct: float = 0.60,
        trail_ladder: tuple[tuple[float, float], ...] = (
            (0.20, 0.00),
            (0.40, 0.20),
            (0.50, 0.35),
        ),
    ) -> None:
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.trail_ladder = trail_ladder

        self._candle2_open: float | None = None
        self._traded_today = False
        self._open_key: str | None = None
        self._sl_level: float | None = None
        self._tgt_level: float | None = None
        self._ladder: list[tuple[float, float]] = []
        self._trail_steps_done = 0

    def on_day_start(self, ctx: Context) -> None:
        self._candle2_open = None
        self._traded_today = False
        self._reset_position()

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        if hhmm == "09:18":
            self._candle2_open = ctx.bar.open

        if self._open_key:
            self._manage(ctx)
            return

        if self._traded_today:
            return

        if hhmm == "09:20" and self._candle2_open is not None:
            close = ctx.bar.close
            option: str | None = None
            if close > self._candle2_open:
                option = "PE"
            elif close < self._candle2_open:
                option = "CE"
            if option:
                key = ctx.buy_option(option_type=option, strike_offset=0, lots=1)
                if key:
                    entry = ctx.portfolio.positions[key].avg_price
                    self._open_key = key
                    self._traded_today = True
                    self._sl_level = entry * (1 - self.sl_pct)
                    self._tgt_level = entry * (1 + self.tgt_pct)
                    self._ladder = [
                        (entry * (1 + trg), entry * (1 + new)) for trg, new in self.trail_ladder
                    ]
                    self._trail_steps_done = 0

    def _manage(self, ctx: Context) -> None:
        if not self._open_key or self._sl_level is None:
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

        while self._trail_steps_done < len(self._ladder) and hi >= self._ladder[self._trail_steps_done][0]:
            new_sl = self._ladder[self._trail_steps_done][1]
            if new_sl > self._sl_level:
                self._sl_level = new_sl
            self._trail_steps_done += 1

    def _reset_position(self) -> None:
        self._open_key = None
        self._sl_level = None
        self._tgt_level = None
        self._ladder = []
        self._trail_steps_done = 0


strategy = Morning3MinMomentum()
