"""Strategy API. Users subclass Strategy and implement on_bar."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

    from backtester.data.instruments import InstrumentResolver
    from backtester.data.reader import DataReader
    from backtester.engine.portfolio import Portfolio


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int = 0


class Context:
    """Injected into on_bar. All strategy state lives here."""

    def __init__(
        self,
        *,
        current_date: date,
        current_bar: Bar,
        reader: DataReader,
        resolver: InstrumentResolver,
        portfolio: Portfolio,
        lot_size: int,
    ) -> None:
        self.date = current_date
        self.bar = current_bar
        self.reader = reader
        self.resolver = resolver
        self.portfolio = portfolio
        self.lot_size = lot_size

    def spot(self) -> float:
        return self.bar.close

    def buy_option(
        self,
        *,
        option_type: str,
        strike_offset: int = 0,
        lots: int = 1,
        expiry: date | None = None,
    ) -> str | None:
        exp = expiry or self.resolver.nearest_expiry(self.date)
        if exp is None:
            return None
        atm = self.resolver.atm_strike(self.spot())
        strike = atm + strike_offset * self.resolver.atm_step
        resolved = self.resolver.resolve(exp, strike, option_type)
        if resolved is None:
            return None
        bars = self.reader.option_bars(resolved.contract.instrument_key, self.date)
        if bars.is_empty():
            return None
        entry_price = self._price_at(bars, self.bar.timestamp)
        if entry_price is None:
            return None
        qty = lots * self.lot_size
        symbol = f"{self.resolver.underlying_key.split('|')[-1]}{exp:%y%m%d}{strike}{option_type}"
        self.portfolio.open(
            instrument_key=resolved.contract.instrument_key,
            symbol=symbol,
            qty=qty,
            price=entry_price,
            ts=self.bar.timestamp,
            is_option=True,
            strike=resolved.contract.strike,
            option_type=option_type,
        )
        return resolved.contract.instrument_key

    def sell_option(self, **kwargs) -> str | None:
        kwargs["lots"] = -abs(kwargs.get("lots", 1))
        return self.buy_option(**kwargs)

    def close(self, instrument_key: str, reason: str = "manual") -> None:
        bars = self.reader.option_bars(instrument_key, self.date)
        exit_price = self._price_at(bars, self.bar.timestamp)
        if exit_price is None:
            return
        self.portfolio.close(instrument_key, exit_price, self.bar.timestamp, reason=reason)

    def close_all(self, reason: str = "square_off") -> None:
        for k in list(self.portfolio.positions.keys()):
            self.close(k, reason=reason)

    @staticmethod
    def _price_at(bars: "pl.DataFrame", ts: datetime) -> float | None:
        if bars.is_empty():
            return None
        matched = bars.filter(bars["timestamp"] == ts)
        if matched.is_empty():
            return float(bars["close"][-1])
        return float(matched["close"][0])


class Strategy(ABC):
    """User strategies subclass this."""

    name: str = "unnamed"

    def on_start(self, ctx: Context) -> None: ...
    def on_day_start(self, ctx: Context) -> None: ...
    def on_day_end(self, ctx: Context) -> None: ...
    def on_end(self, ctx: Context) -> None: ...

    @abstractmethod
    def on_bar(self, ctx: Context) -> None: ...
