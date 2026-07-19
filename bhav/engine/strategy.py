"""Strategy API. Users subclass Strategy and implement on_bar."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl

    from bhav.data.instruments import InstrumentResolver
    from bhav.data.reader import DataReader
    from bhav.engine.portfolio import Portfolio


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
        is_warmup: bool = False,
        allow_new_orders: bool = True,
        atm_ref_price: float | None = None,
    ) -> None:
        self.date = current_date
        self.bar = current_bar
        self.reader = reader
        self.resolver = resolver
        self.portfolio = portfolio
        self.lot_size = lot_size
        self.is_warmup = is_warmup
        self.allow_new_orders = allow_new_orders
        self._atm_ref_price = atm_ref_price

    def spot(self) -> float:
        return self.bar.close

    def atm_reference_price(self) -> float:
        """The price used to pick the ATM strike.

        Defaults to spot, but the engine overrides it with the futures price when
        run with `atm_reference="futures"`. NIFTY options are priced off the
        future, so choosing ATM off the raw spot index is biased by the basis
        (the future usually trades at a small premium/discount to spot). Use this,
        not `spot()`, whenever you round to a strike.
        """
        return self._atm_ref_price if self._atm_ref_price is not None else self.spot()

    def buy_option(
        self,
        *,
        option_type: str,
        strike_offset: int = 0,
        lots: int = 1,
        expiry: date | None = None,
    ) -> str | None:
        if self.is_warmup or not self.allow_new_orders:
            return None
        exp = expiry or self.resolver.nearest_expiry(self.date)
        if exp is None:
            return None
        atm = self.resolver.atm_strike(self.atm_reference_price())
        strike = atm + strike_offset * self.resolver.atm_step
        resolved = self.resolver.resolve(exp, strike, option_type, on_date=self.date)
        if resolved is None:
            return None
        bars = self.reader.option_bars(resolved.contract.instrument_key, self.date)
        if bars.is_empty():
            return None
        entry_price = self._price_at(bars, self.bar.timestamp)
        if entry_price is None:
            return None
        qty = lots * self.lot_size
        if qty > 0 and entry_price * qty > self.portfolio.cash:
            return None  # can't afford the premium; reject like any other failed fill
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

    def close(
        self, instrument_key: str, reason: str = "manual", lots: int | None = None
    ) -> None:
        """Close a position. By default the whole key; pass `lots` to close only
        that many lots (a single tranche) and leave the rest open."""
        if self.is_warmup:
            return
        bars = self.reader.option_bars(instrument_key, self.date)
        exit_price = self._price_at(bars, self.bar.timestamp)
        if exit_price is None:
            return
        qty = lots * self.lot_size if lots is not None else None
        self.portfolio.close(
            instrument_key, exit_price, self.bar.timestamp, reason=reason, qty=qty
        )

    def close_all(self, reason: str = "square_off") -> None:
        for k in list(self.portfolio.positions.keys()):
            self.close(k, reason=reason)

    @staticmethod
    def _price_at(bars: "pl.DataFrame", ts: datetime) -> float | None:
        """Close of the bar at `ts`, else the most recent bar BEFORE it.
        Never a later bar - that would be lookahead. None if nothing has
        traded yet by `ts`."""
        if bars.is_empty():
            return None
        at_or_before = bars.filter(bars["timestamp"] <= ts)
        if at_or_before.is_empty():
            return None
        return float(at_or_before["close"][-1])


class Strategy(ABC):
    """User strategies subclass this."""

    name: str = "unnamed"

    def on_start(self, ctx: Context) -> None: ...
    def on_day_start(self, ctx: Context) -> None: ...
    def on_day_end(self, ctx: Context) -> None: ...
    def on_end(self, ctx: Context) -> None: ...

    @abstractmethod
    def on_bar(self, ctx: Context) -> None: ...
