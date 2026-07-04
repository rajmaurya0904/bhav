"""Portfolio: positions, MTM, trades, equity curve."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backtester.engine.costs import CostBreakdown, CostModel


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


@dataclass
class Portfolio:
    starting_capital: float
    cost_model: CostModel
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    closed_trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
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
        cb = self.cost_model.costs(price, abs(qty), is_buy=is_buy)
        self.cash -= price * qty + cb.total
        self._total_costs += cb.total
        pos = Position(
            instrument_key=instrument_key,
            symbol=symbol,
            qty=qty,
            avg_price=price,
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
        cb = self.cost_model.costs(
            price, abs(pos.qty), is_buy=is_buy_close, exercised_itm=exercised_itm
        )
        self.cash += price * pos.qty + (-cb.total)
        self._total_costs += cb.total
        pnl_gross = (price - pos.avg_price) * pos.qty
        trade = Trade(
            symbol=pos.symbol,
            instrument_key=instrument_key,
            entry_time=pos.entry_time,
            exit_time=ts,
            qty=pos.qty,
            entry_price=pos.avg_price,
            exit_price=price,
            pnl_gross=pnl_gross,
            costs=cb.total,
            pnl_net=pnl_gross - cb.total,
            reason=reason,
        )
        self.closed_trades.append(trade)
        return trade

    def mark(self, ts: datetime, marks: dict[str, float]) -> float:
        mtm = sum(pos.mtm(marks.get(k, pos.avg_price)) for k, pos in self.positions.items())
        equity = self.cash + mtm + sum(
            pos.avg_price * pos.qty for pos in self.positions.values()
        )
        self.equity_curve.append((ts, equity))
        return equity

    @property
    def total_costs(self) -> float:
        return self._total_costs
