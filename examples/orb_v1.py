"""ORB v1 reference strategy, ported to the engine API.

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
        session_end: str = "12:00",
    ) -> None:
        self.mode = mode
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.session_end = session_end
        self._orh: float | None = None
        self._orl: float | None = None
        self._in_trade = False
        self._entry_price: float | None = None
        self._open_key: str | None = None

    def on_day_start(self, ctx: Context) -> None:
        self._orh = None
        self._orl = None
        self._in_trade = False
        self._entry_price = None
        self._open_key = None

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if "09:15" <= hhmm < "09:30":
            self._orh = ctx.bar.high if self._orh is None else max(self._orh, ctx.bar.high)
            self._orl = ctx.bar.low if self._orl is None else min(self._orl, ctx.bar.low)
            return
        if self._orh is None or self._orl is None:
            return
        if self._in_trade:
            self._manage(ctx)
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
                self._in_trade = True
                self._open_key = key
                self._entry_price = ctx.portfolio.positions[key].avg_price

    def _manage(self, ctx: Context) -> None:
        if not self._entry_price or not self._open_key:
            return
        pos = ctx.portfolio.positions.get(self._open_key)
        if pos is None:
            self._in_trade = False
            return
        bars = ctx.reader.option_bars(self._open_key, ctx.date)
        row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
        if row.is_empty():
            return
        hi = float(row["high"][0])
        lo = float(row["low"][0])
        sl = self._entry_price * (1 - self.sl_pct)
        tgt = self._entry_price * (1 + self.tgt_pct)
        if lo <= sl:
            ctx.close(self._open_key, reason="sl_hit")
            self._reset()
        elif hi >= tgt:
            ctx.close(self._open_key, reason="tgt_hit")
            self._reset()

    def _reset(self) -> None:
        self._in_trade = False
        self._entry_price = None
        self._open_key = None


strategy = OpeningRangeBreakout(mode="FADE")
