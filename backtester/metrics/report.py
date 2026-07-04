"""Metrics: CAGR, Sharpe, Sortino, max DD, win rate, expectancy."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from backtester.engine.portfolio import Portfolio, Trade


@dataclass
class MetricsReport:
    starting_capital: float
    ending_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    max_drawdown_amount: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    total_costs: float
    exposure_time_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


def _returns(equity: list[tuple[datetime, float]]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(equity)):
        prev = equity[i - 1][1]
        if prev == 0:
            continue
        out.append((equity[i][1] - prev) / prev)
    return out


def _max_dd(equity: list[tuple[datetime, float]]) -> tuple[float, float]:
    peak = -math.inf
    max_dd_pct = 0.0
    max_dd_amt = 0.0
    for _, v in equity:
        peak = max(peak, v)
        dd = peak - v
        dd_pct = dd / peak if peak else 0.0
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            max_dd_amt = dd
    return max_dd_pct * 100, max_dd_amt


def _sharpe(rets: list[float], periods_per_year: int = 252 * 375) -> float:
    if not rets:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)


def _sortino(rets: list[float], periods_per_year: int = 252 * 375) -> float:
    if not rets:
        return 0.0
    mean = sum(rets) / len(rets)
    downside = [r for r in rets if r < 0]
    if not downside:
        return 0.0
    dvar = sum(r * r for r in downside) / len(rets)
    dstd = math.sqrt(dvar)
    if dstd == 0:
        return 0.0
    return (mean / dstd) * math.sqrt(periods_per_year)


def compute_metrics(portfolio: Portfolio) -> MetricsReport:
    equity = portfolio.equity_curve
    if not equity:
        equity = [(datetime.now(), portfolio.starting_capital)]
    ending = equity[-1][1]
    total_return = (ending - portfolio.starting_capital) / portfolio.starting_capital * 100
    days = max((equity[-1][0] - equity[0][0]).days, 1)
    years = days / 365.25
    cagr = ((ending / portfolio.starting_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
    rets = _returns(equity)
    max_dd_pct, max_dd_amt = _max_dd(equity)
    trades: list[Trade] = portfolio.closed_trades
    wins = [t for t in trades if t.pnl_net > 0]
    losses = [t for t in trades if t.pnl_net <= 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    avg_win = sum(t.pnl_net for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl_net for t in losses) / len(losses) if losses else 0.0
    gross_win = sum(t.pnl_net for t in wins)
    gross_loss = abs(sum(t.pnl_net for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else 0.0
    expectancy = (
        (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
        if trades else 0.0
    )
    bars_with_position = sum(1 for _, v in equity if v != portfolio.starting_capital)
    exposure_pct = (bars_with_position / len(equity) * 100) if equity else 0.0
    return MetricsReport(
        starting_capital=portfolio.starting_capital,
        ending_equity=ending,
        total_return_pct=total_return,
        cagr_pct=cagr,
        sharpe=_sharpe(rets),
        sortino=_sortino(rets),
        max_drawdown_pct=max_dd_pct,
        max_drawdown_amount=max_dd_amt,
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate_pct=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=pf,
        expectancy=expectancy,
        total_costs=portfolio.total_costs,
        exposure_time_pct=exposure_pct,
    )
