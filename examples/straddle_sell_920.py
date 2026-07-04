"""At 09:20 every day, sell one ATM straddle (CE + PE). Cut both legs if combined
loss reaches 30% of premium received. Engine handles the 15:15 square-off.

Generated to test multi-leg management via the AI-prompt contract.
"""
from bhav.engine.strategy import Context, Strategy


class Straddle920(Strategy):
    name = "straddle_sell_0920"

    def __init__(self, max_loss_pct: float = 0.30):
        self.max_loss_pct = max_loss_pct
        self._ce: str | None = None
        self._pe: str | None = None
        self._premium: float = 0.0
        self._entered = False

    def on_day_start(self, ctx: Context) -> None:
        self._ce = None
        self._pe = None
        self._premium = 0.0
        self._entered = False

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"

        if not self._entered and hhmm == "09:20":
            ce = ctx.sell_option(option_type="CE", strike_offset=0, lots=1)
            pe = ctx.sell_option(option_type="PE", strike_offset=0, lots=1)
            if ce and pe:
                self._ce = ce
                self._pe = pe
                self._premium = (
                    ctx.portfolio.positions[ce].avg_price
                    + ctx.portfolio.positions[pe].avg_price
                )
                self._entered = True
            return

        if self._ce is None or self._pe is None:
            return

        current = 0.0
        for k in (self._ce, self._pe):
            if k not in ctx.portfolio.positions:
                continue
            bars = ctx.reader.option_bars(k, ctx.date)
            row = bars.filter(bars["timestamp"] == ctx.bar.timestamp)
            if row.is_empty():
                return
            current += float(row["close"][0])

        loss = current - self._premium
        if loss >= self.max_loss_pct * self._premium:
            ctx.close_all(reason="loss_cap_hit")
            self._ce = None
            self._pe = None


strategy = Straddle920(max_loss_pct=0.30)
