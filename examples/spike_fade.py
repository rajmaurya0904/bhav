"""Spike-fade: when NIFTY moves >= 40 points in a single 1-min bar during 09:30-13:30,
buy the OPPOSITE ATM option (fade the move). 30% SL, 60% target. Max 3 trades per day.

Generated to test intra-day signal detection and repeated entries.
"""
from bhav.engine.strategy import Context, Strategy


class SpikeFade(Strategy):
    name = "spike_fade"

    def __init__(
        self,
        spike_points: float = 40.0,
        sl_pct: float = 0.30,
        tgt_pct: float = 0.60,
        max_trades: int = 3,
    ):
        self.spike_points = spike_points
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.max_trades = max_trades
        self._trades_today = 0
        self._open_key: str | None = None
        self._entry: float | None = None

    def on_day_start(self, ctx: Context) -> None:
        self._trades_today = 0
        self._open_key = None
        self._entry = None

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        # Management first
        if self._open_key and self._entry:
            bars = ctx.reader.option_bars(self._open_key, ctx.date)
            row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
            if not row.is_empty():
                hi, lo = float(row["high"][0]), float(row["low"][0])
                if lo <= self._entry * (1 - self.sl_pct):
                    ctx.close(self._open_key, reason="sl_hit")
                    self._open_key = None
                    self._entry = None
                elif hi >= self._entry * (1 + self.tgt_pct):
                    ctx.close(self._open_key, reason="tgt_hit")
                    self._open_key = None
                    self._entry = None

        # Entry window: 09:30 to 13:30
        if hhmm < "09:30" or hhmm > "13:30":
            return
        if self._open_key or self._trades_today >= self.max_trades:
            return

        bar_move = ctx.bar.close - ctx.bar.open
        option: str | None = None
        if bar_move >= self.spike_points:
            option = "PE"   # fade the upward spike
        elif bar_move <= -self.spike_points:
            option = "CE"   # fade the downward spike
        if option:
            key = ctx.buy_option(option_type=option, strike_offset=0, lots=1)
            if key:
                self._open_key = key
                self._entry = ctx.portfolio.positions[key].avg_price
                self._trades_today += 1


strategy = SpikeFade(spike_points=40.0, sl_pct=0.30, tgt_pct=0.60, max_trades=3)
