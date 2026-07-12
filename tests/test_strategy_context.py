"""Regression tests for Context._price_at lookahead and metrics edge cases."""
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from bhav.engine.costs import IndianCostModel
from bhav.engine.portfolio import Portfolio
from bhav.engine.strategy import Context
from bhav.metrics.report import compute_metrics, _sortino

IST = ZoneInfo("Asia/Kolkata")


def _bars(rows):
    return pl.DataFrame(
        {"timestamp": [r[0] for r in rows], "close": [float(r[1]) for r in rows]}
    )


def test_price_at_exact_bar():
    bars = _bars([(datetime(2025, 8, 1, 9, 30, tzinfo=IST), 100.0)])
    assert Context._price_at(bars, datetime(2025, 8, 1, 9, 30, tzinfo=IST)) == 100.0


def test_price_at_missing_bar_uses_earlier_never_later():
    bars = _bars(
        [
            (datetime(2025, 8, 1, 9, 30, tzinfo=IST), 100.0),
            (datetime(2025, 8, 1, 15, 29, tzinfo=IST), 55.0),
        ]
    )
    # 10:00 has no bar: must fall back to 09:30 (100), NOT 15:29 (55)
    assert Context._price_at(bars, datetime(2025, 8, 1, 10, 0, tzinfo=IST)) == 100.0


def test_price_at_before_first_bar_returns_none():
    bars = _bars([(datetime(2025, 8, 1, 9, 30, tzinfo=IST), 100.0)])
    assert Context._price_at(bars, datetime(2025, 8, 1, 9, 15, tzinfo=IST)) is None


def test_profit_factor_none_when_no_losses():
    p = Portfolio(starting_capital=100_000, cost_model=IndianCostModel(slippage_ticks=0.0))
    ts = datetime(2025, 8, 1, 9, 30)
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=ts)
    p.close("K", 200.0, ts)
    m = compute_metrics(p)
    assert m.winning_trades == 1
    assert m.profit_factor is None  # not 0.0


def test_sortino_none_when_no_downside():
    assert _sortino([0.01, 0.02, 0.01]) is None


def test_scratch_trade_not_counted_as_loss():
    class FreeModel(IndianCostModel):
        def costs(self, price, qty, is_buy, exercised_itm=False):
            from bhav.engine.costs import CostBreakdown
            return CostBreakdown()

    p = Portfolio(starting_capital=100_000, cost_model=FreeModel(slippage_ticks=0.0))
    ts = datetime(2025, 8, 1, 9, 30)
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=ts)
    p.close("K", 100.0, ts)  # exactly zero P&L
    m = compute_metrics(p)
    assert m.winning_trades == 0
    assert m.losing_trades == 0
    assert m.total_trades == 1
