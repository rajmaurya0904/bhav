"""Portfolio: positions, MTM, trades, equity curve."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from bhav.engine.costs import CostBreakdown, CostModel


@dataclass
class Position:
    instrument_key: str
    symbol: str
    qty: int
    avg_price: float
    entry_time: datetime
    is_option: bool = False
    strike: int | None = None
    option_type: str | None = None

    def mtm(self, mark: float) -> float:
        return (mark - self.avg_price) * self.qty


@dataclass
class Trade:
    symbol: str
    instrument_key: str
    entry_time: datetime
    exit_time: datetime
    qty: int
    entry_price: float
    exit_price: float
    pnl_gross: float
    costs: float
    pnl_net: float
    reason: str
    tags: dict = field(default_factory=dict)


class OppositeSideError(ValueError):
    """Raised when an open() would flip an existing position's direction.

    Reducing/reversing through open() silently corrupts avg-price accounting;
    close the position first, then open the new side.
    """


@dataclass
class Portfolio:
    starting_capital: float
    cost_model: CostModel
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    closed_trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    exposure_curve: list[bool] = field(default_factory=list)
    _total_costs: float = 0.0

    def __post_init__(self) -> None:
        if self.cash == 0.0:
            self.cash = self.starting_capital

    def open(
        self,
        *,
        instrument_key: str,
        symbol: str,
        qty: int,
        price: float,
        ts: datetime,
        is_option: bool = False,
        strike: int | None = None,
        option_type: str | None = None,
    ) -> Position:
        is_buy = qty > 0
        fill = self.cost_model.fill_price(price, is_buy=is_buy)
        cb = self.cost_model.costs(fill, abs(qty), is_buy=is_buy)
        self.cash -= fill * qty + cb.total
        self._total_costs += cb.total
        existing = self.positions.get(instrument_key)
        if existing is not None:
            if (existing.qty > 0) != is_buy:
                raise OppositeSideError(
                    f"open() on {instrument_key} would reduce/flip an existing "
                    f"{existing.qty:+d} position; close it first"
                )
            total_qty = existing.qty + qty
            existing.avg_price = (
                existing.avg_price * existing.qty + fill * qty
            ) / total_qty
            existing.qty = total_qty
            return existing
        pos = Position(
            instrument_key=instrument_key,
            symbol=symbol,
            qty=qty,
            avg_price=fill,
            entry_time=ts,
            is_option=is_option,
            strike=strike,
            option_type=option_type,
        )
        self.positions[instrument_key] = pos
        return pos

    def close(
        self,
        instrument_key: str,
        price: float,
        ts: datetime,
        reason: str = "manual",
        exercised_itm: bool = False,
    ) -> Trade | None:
        pos = self.positions.pop(instrument_key, None)
        if pos is None:
            return None
        is_buy_close = pos.qty < 0
        fill = self.cost_model.fill_price(price, is_buy=is_buy_close)
        cb = self.cost_model.costs(
            fill, abs(pos.qty), is_buy=is_buy_close, exercised_itm=exercised_itm
        )
        self.cash += fill * pos.qty + (-cb.total)
        self._total_costs += cb.total
        pnl_gross = (fill - pos.avg_price) * pos.qty
        trade = Trade(
            symbol=pos.symbol,
            instrument_key=instrument_key,
            entry_time=pos.entry_time,
            exit_time=ts,
            qty=pos.qty,
            entry_price=pos.avg_price,
            exit_price=fill,
            pnl_gross=pnl_gross,
            costs=cb.total,
            pnl_net=pnl_gross - cb.total,
            reason=reason,
        )
        self.closed_trades.append(trade)
        return trade

    def mark(self, ts: datetime, marks: dict[str, float]) -> float:
        """Record an equity point. `marks` maps instrument_key -> current price;
        positions missing from `marks` fall back to entry price (stale mark)."""
        equity = self.cash + sum(
            marks.get(k, pos.avg_price) * pos.qty for k, pos in self.positions.items()
        )
        self.equity_curve.append((ts, equity))
        self.exposure_curve.append(bool(self.positions))
        return equity

    @property
    def total_costs(self) -> float:
        return self._total_costs
