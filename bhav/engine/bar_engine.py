"""Per-day 1-minute event loop."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from bhav.data.calendar import NSECalendar
from bhav.data.instruments import InstrumentResolver
from bhav.data.reader import DataReader
from bhav.data.underlyings import default_lot_size
from bhav.engine.costs import CostModel, IndianCostModel
from bhav.engine.portfolio import Portfolio
from bhav.engine.strategy import Bar, Context, Strategy


@dataclass
class EngineConfig:
    underlying_key: str
    start: date
    end: date
    starting_capital: float = 500_000
    lot_size: int | None = None  # None = auto-lookup from underlying_key
    interval: str = "1minute"
    cost_model: CostModel | None = None
    calendar: NSECalendar | None = None
    square_off_time: str = "15:15"
    warmup_days: int = 0  # trading days to feed into the strategy before the backtest window
    # "spot" or "futures": which price picks the ATM strike
    atm_reference: str = "spot"
    # instrument key of a specific future; pins the contract for the whole run
    futures_key: str | None = None
    # auto-roll the front-month future per day (via a FuturesRoll passed to the
    # engine) instead of pinning one futures_key
    futures_auto: bool = False

    def resolved_lot_size(self) -> int:
        return self.lot_size if self.lot_size is not None else default_lot_size(self.underlying_key)

    def __post_init__(self) -> None:
        if self.atm_reference not in ("spot", "futures"):
            raise ValueError(
                f"atm_reference must be 'spot' or 'futures', got {self.atm_reference!r}"
            )
        if self.atm_reference == "futures" and not self.futures_key and not self.futures_auto:
            raise ValueError(
                "atm_reference='futures' requires futures_key to be set (or futures_auto=True)"
            )


class BarEngine:
    def __init__(
        self,
        cfg: EngineConfig,
        reader: DataReader,
        resolver: InstrumentResolver,
        futures_roll=None,
    ) -> None:
        self.cfg = cfg
        self.reader = reader
        self.resolver = resolver
        # front-month roller for atm_reference="futures" when no fixed key is set
        self.futures_roll = futures_roll
        if cfg.atm_reference == "futures" and not cfg.futures_key and futures_roll is None:
            raise ValueError(
                "atm_reference='futures' needs either cfg.futures_key or a futures_roll"
            )
        self.calendar = cfg.calendar or NSECalendar()
        self.portfolio = Portfolio(
            starting_capital=cfg.starting_capital,
            cost_model=cfg.cost_model or IndianCostModel(),
        )

    def _warmup_dates(self) -> list[date]:
        if self.cfg.warmup_days <= 0:
            return []
        out: list[date] = []
        cursor = self.cfg.start - timedelta(days=1)
        while len(out) < self.cfg.warmup_days and cursor > self.cfg.start - timedelta(days=45):
            if self.calendar.is_trading_day(cursor):
                out.append(cursor)
            cursor -= timedelta(days=1)
        out.reverse()
        return out

    def _mark_prices(self, d, ts, day_bars_memo: dict) -> dict[str, float]:
        """Current price for every open position, for mark-to-market.
        Bars are memoized per (instrument, day) so marking costs one cache
        read per instrument per day, not one per bar."""
        marks: dict[str, float] = {}
        for key in self.portfolio.positions:
            if key not in day_bars_memo:
                day_bars_memo[key] = self.reader.option_bars(key, d, self.cfg.interval)
            px = Context._price_at(day_bars_memo[key], ts)
            if px is not None:
                marks[key] = px
        return marks

    def run(self, strategy: Strategy) -> Portfolio:
        warmup_days = self._warmup_dates()
        live_days = self.calendar.trading_days(self.cfg.start, self.cfg.end)
        lot_size = self.cfg.resolved_lot_size()
        first_ctx: Context | None = None

        for phase_days, is_warmup in ((warmup_days, True), (live_days, False)):
            for d in phase_days:
                spot = self.reader.spot_bars(self.cfg.underlying_key, d, self.cfg.interval)
                if spot.is_empty():
                    continue
                # For futures-basis ATM, pull the future's candles for the day once.
                # Endpoint 1 (get_index_candles) serves both spot indices and futures.
                # A pinned futures_key wins; otherwise roll to the front month for `d`.
                futures = None
                if self.cfg.atm_reference == "futures":
                    fut_key = self.cfg.futures_key
                    if fut_key is None and self.futures_roll is not None:
                        fut_key = self.futures_roll.front_month(d)
                    if fut_key:
                        fut = self.reader.spot_bars(fut_key, d, self.cfg.interval)
                        futures = fut if not fut.is_empty() else None
                day_ctx: Context | None = None
                squared_off = False
                day_bars_memo: dict = {}
                for row in spot.iter_rows(named=True):
                    bar = Bar(
                        timestamp=row["timestamp"],
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=row["volume"],
                        oi=row["oi"],
                    )
                    hhmm = f"{bar.timestamp.hour:02d}:{bar.timestamp.minute:02d}"
                    past_square_off = hhmm >= self.cfg.square_off_time
                    # ATM reference: futures price at this bar if available, else spot.
                    atm_ref = None
                    if futures is not None:
                        atm_ref = Context._price_at(futures, bar.timestamp)
                    ctx = Context(
                        current_date=d,
                        current_bar=bar,
                        reader=self.reader,
                        resolver=self.resolver,
                        portfolio=self.portfolio,
                        lot_size=lot_size,
                        is_warmup=is_warmup,
                        allow_new_orders=not past_square_off,
                        atm_ref_price=atm_ref,
                    )
                    if first_ctx is None:
                        strategy.on_start(ctx)
                        first_ctx = ctx
                    # First bar of the day, whatever its clock time. Keying this
                    # to an exact "09:15" bar broke day-state resets on feed gaps.
                    if day_ctx is None:
                        strategy.on_day_start(ctx)
                    if past_square_off and not squared_off and not is_warmup:
                        ctx.close_all(reason="eod_square_off")
                        squared_off = True
                    strategy.on_bar(ctx)
                    if not is_warmup:
                        marks = self._mark_prices(d, bar.timestamp, day_bars_memo)
                        self.portfolio.mark(bar.timestamp, marks)
                    day_ctx = ctx
                if day_ctx is not None:
                    # Backstop: engine semantics are daily-flat. If the feed had
                    # no bar at/after square_off_time, flatten at the last bar.
                    if not is_warmup and self.portfolio.positions:
                        day_ctx.close_all(reason="eod_square_off")
                    strategy.on_day_end(day_ctx)

        if first_ctx is not None:
            strategy.on_end(first_ctx)
        return self.portfolio
