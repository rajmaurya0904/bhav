"""Morning-momentum: at 09:30, if NIFTY is up >= 25 points from open, buy ATM CE;
if down >= 25 points, buy ATM PE. 25% SL, 50% target on premium. One trade per day.

Generated to test the AI-prompt strategy contract on real data.
"""
from bhav.engine.strategy import Context, Strategy


class MorningMomentum(Strategy):
    name = "morning_momentum"

    def __init__(self, threshold: float = 25.0, sl_pct: float = 0.25, tgt_pct: float = 0.50):
        self.threshold = threshold
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self._day_open: float | None = None
        self._entered = False
        self._open_key: str | None = None
        self._entry: float | None = None

    def on_day_start(self, ctx: Context) -> None:
        self._day_open = None
        self._entered = False
        self._open_key = None
        self._entry = None

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        if self._day_open is None and hhmm == "09:15":
            self._day_open = ctx.bar.open

        if not self._entered and hhmm == "09:30" and self._day_open is not None:
            move = ctx.bar.close - self._day_open
            option: str | None = None
            if move >= self.threshold:
                option = "CE"
            elif move <= -self.threshold:
                option = "PE"
            if option:
                key = ctx.buy_option(option_type=option, strike_offset=0, lots=1)
                if key:
                    self._open_key = key
                    self._entry = ctx.portfolio.positions[key].avg_price
                    self._entered = True
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
                self._entry = None
            elif hi >= self._entry * (1 + self.tgt_pct):
                ctx.close(self._open_key, reason="tgt_hit")
                self._open_key = None
                self._entry = None


strategy = MorningMomentum(threshold=25.0, sl_pct=0.25, tgt_pct=0.50)
