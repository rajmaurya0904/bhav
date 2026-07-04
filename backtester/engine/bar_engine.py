"""Per-day 1-minute event loop."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backtester.data.calendar import NSECalendar
from backtester.data.instruments import InstrumentResolver
from backtester.data.reader import DataReader
from backtester.engine.costs import CostModel, IndianCostModel
from backtester.engine.portfolio import Portfolio
from backtester.engine.strategy import Bar, Context, Strategy


@dataclass
class EngineConfig:
    underlying_key: str
    start: date
    end: date
    starting_capital: float = 500_000
    lot_size: int = 75
    interval: str = "1minute"
    cost_model: CostModel | None = None
    calendar: NSECalendar | None = None
    square_off_time: str = "15:15"


class BarEngine:
    def __init__(
        self,
        cfg: EngineConfig,
        reader: DataReader,
        resolver: InstrumentResolver,
    ) -> None:
        self.cfg = cfg
        self.reader = reader
        self.resolver = resolver
        self.calendar = cfg.calendar or NSECalendar()
        self.portfolio = Portfolio(
            starting_capital=cfg.starting_capital,
            cost_model=cfg.cost_model or IndianCostModel(),
        )

    def run(self, strategy: Strategy) -> Portfolio:
        days = self.calendar.trading_days(self.cfg.start, self.cfg.end)
        first_ctx: Context | None = None
        for d in days:
            spot = self.reader.spot_bars(self.cfg.underlying_key, d, self.cfg.interval)
            if spot.is_empty():
                continue
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
                ctx = Context(
                    current_date=d,
                    current_bar=bar,
                    reader=self.reader,
                    resolver=self.resolver,
                    portfolio=self.portfolio,
                    lot_size=self.cfg.lot_size,
                )
                if first_ctx is None:
                    strategy.on_start(ctx)
                    first_ctx = ctx
                hhmm = f"{bar.timestamp.hour:02d}:{bar.timestamp.minute:02d}"
                if hhmm == "09:15":
                    strategy.on_day_start(ctx)
                strategy.on_bar(ctx)
                if hhmm == self.cfg.square_off_time:
                    ctx.close_all(reason="eod_square_off")
                self.portfolio.mark(bar.timestamp, {})
            strategy.on_day_end(ctx)
        if first_ctx is not None:
            strategy.on_end(first_ctx)
        return self.portfolio
