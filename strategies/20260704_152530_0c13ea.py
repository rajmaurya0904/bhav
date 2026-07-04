from bhav.engine.strategy import Context, Strategy


class MyStrategy(Strategy):
    """
    2/3-day rolling S/R FADE strategy.

    Resistance/Support = highest-high / lowest-low of the last `lookback_days`
    completed trading days (rolling, always excludes the current day).

    Entry (one trade per day, first qualifying bar wins):
        - Spot 1-min CLOSE breaks ABOVE Resistance -> fade it -> Buy ATM PE
        - Spot 1-min CLOSE breaks BELOW Support    -> fade it -> Buy ATM CE

    Exit:
        - Initial SL at sl_pct below entry premium
        - Target at tgt_pct above entry premium
        - Trailing-SL ladder tightens the stop as premium runs in favor
        - Auto square-off at 15:15 is handled by the engine (not duplicated here)
    """

    name = "sr_fade_lb3_v1"

    def __init__(
        self,
        lookback_days: int = 3,
        sl_pct: float = 0.30,
        tgt_pct: float = 0.60,
        trail_ladder=((0.20, 0.00), (0.40, 0.20), (0.50, 0.35)),
    ):
        self.lookback_days = lookback_days
        self.sl_pct = sl_pct
        self.tgt_pct = tgt_pct
        self.trail_ladder = trail_ladder

        # cross-day rolling memory (NOT reset per day)
        self._day_history = []  # list of (day_high, day_low), most recent last

        # per-day state (reset in on_day_start)
        self._resistance = None
        self._support = None
        self._today_high = float("-inf")
        self._today_low = float("inf")
        self._traded_today = False
        self._open_key = None
        self._entry = None
        self._sl_level = None
        self._tgt_level = None
        self._trail_steps_done = 0
        self._ladder = []

    def on_day_start(self, ctx: Context) -> None:
        self._today_high = float("-inf")
        self._today_low = float("inf")
        self._traded_today = False
        self._open_key = None
        self._entry = None
        self._sl_level = None
        self._tgt_level = None
        self._trail_steps_done = 0
        self._ladder = []

        if len(self._day_history) >= self.lookback_days:
            window = self._day_history[-self.lookback_days:]
            self._resistance = max(h for h, l in window)
            self._support = min(l for h, l in window)
        else:
            self._resistance = None
            self._support = None

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        if ctx.bar.high > self._today_high:
            self._today_high = ctx.bar.high
        if ctx.bar.low < self._today_low:
            self._today_low = ctx.bar.low

        # ── manage an already-open position, every bar ──
        if self._open_key is not None:
            bars = ctx.reader.option_bars(self._open_key, ctx.date)
            row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
            if row.is_empty():
                return
            hi, lo = float(row["high"][0]), float(row["low"][0])

            if lo <= self._sl_level:
                reason = "trail_sl" if self._trail_steps_done > 0 else "sl_hit"
                ctx.close(self._open_key, reason=reason)
                self._open_key = None
                return

            if hi >= self._tgt_level:
                ctx.close(self._open_key, reason="tgt_hit")
                self._open_key = None
                return

            while (self._trail_steps_done < len(self._ladder)
                   and hi >= self._ladder[self._trail_steps_done][0]):
                new_sl = self._ladder[self._trail_steps_done][1]
                if new_sl > self._sl_level:
                    self._sl_level = new_sl
                self._trail_steps_done += 1
            return

        # ── look for an entry, once per day, within the session window ──
        if self._traded_today or self._resistance is None:
            return
        if hhmm < "09:15" or hhmm > "15:14":
            return

        close = ctx.spot()
        if close > self._resistance:
            option_type = "PE"
        elif close < self._support:
            option_type = "CE"
        else:
            return

        key = ctx.buy_option(option_type=option_type, strike_offset=0, lots=1)
        if key is None:
            return

        entry = ctx.portfolio.positions[key].avg_price
        self._open_key = key
        self._entry = entry
        self._sl_level = entry * (1 - self.sl_pct)
        self._tgt_level = entry * (1 + self.tgt_pct)
        self._trail_steps_done = 0
        self._ladder = [(entry * (1 + trg), entry * (1 + new))
                         for trg, new in self.trail_ladder]
        self._traded_today = True

    def on_day_end(self, ctx: Context) -> None:
        if self._today_high != float("-inf"):
            self._day_history.append((self._today_high, self._today_low))
            self._day_history = self._day_history[-self.lookback_days:]


strategy = MyStrategy(lookback_days=3, sl_pct=0.30, tgt_pct=0.60)
