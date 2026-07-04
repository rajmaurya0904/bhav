"""ORB v1 FADE strategy."""
from bhav.engine.strategy import Context, Strategy


class OpeningRangeBreakout(Strategy):
    name = "orb_v1_ui_test"

    def __init__(self, sl_pct=0.30, tgt_pct=0.60, session_end="12:00"):
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.session_end = session_end
        self._orh = None
        self._orl = None
        self._in_trade = False
        self._entry_price = None
        self._open_key = None

    def on_day_start(self, ctx):
        self._orh = None
        self._orl = None
        self._in_trade = False
        self._entry_price = None
        self._open_key = None

    def on_bar(self, ctx):
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if "09:15" <= hhmm < "09:30":
            self._orh = ctx.bar.high if self._orh is None else max(self._orh, ctx.bar.high)
            self._orl = ctx.bar.low if self._orl is None else min(self._orl, ctx.bar.low)
            return
        if self._orh is None or self._orl is None:
            return
        if self._in_trade:
            self._manage(ctx); return
        if hhmm >= self.session_end:
            return
        close = ctx.bar.close
        signal = None
        if close > self._orh:
            signal = "PE"
        elif close < self._orl:
            signal = "CE"
        if signal:
            key = ctx.buy_option(option_type=signal, strike_offset=0, lots=1)
            if key:
                self._in_trade = True
                self._open_key = key
                self._entry_price = ctx.portfolio.positions[key].avg_price

    def _manage(self, ctx):
        if not self._entry_price or not self._open_key:
            return
        if self._open_key not in ctx.portfolio.positions:
            self._in_trade = False; return
        bars = ctx.reader.option_bars(self._open_key, ctx.date)
        row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
        if row.is_empty():
            return
        hi = float(row["high"][0]); lo = float(row["low"][0])
        sl = self._entry_price * (1 - self.sl_pct)
        tgt = self._entry_price * (1 + self.tgt_pct)
        if lo <= sl:
            ctx.close(self._open_key, reason="sl_hit"); self._reset()
        elif hi >= tgt:
            ctx.close(self._open_key, reason="tgt_hit"); self._reset()

    def _reset(self):
        self._in_trade = False; self._entry_price = None; self._open_key = None


strategy = OpeningRangeBreakout()
