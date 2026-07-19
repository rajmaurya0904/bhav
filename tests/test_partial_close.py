"""Partial (tranche) close: closing N contracts of an aggregated position.

Addresses the v0.1 feedback that multiple entries blend into one instrument_key
(always the case in excel mode) and ctx.close() dumped the whole key. Now a
strategy can peel off a single tranche.
"""
from datetime import datetime

import pytest

from bhav.engine.costs import IndianCostModel
from bhav.engine.portfolio import Portfolio

TS = datetime(2025, 8, 1, 9, 30)


class NoFriction(IndianCostModel):
    def __init__(self):
        super().__init__(slippage_ticks=0.0)


def _pf(capital=1_000_000.0):
    return Portfolio(starting_capital=capital, cost_model=NoFriction())


def test_partial_close_leaves_remainder_open():
    p = _pf()
    # two entries blend into one 130-lot long at avg 105
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    p.open(instrument_key="K", symbol="S", qty=65, price=110.0, ts=TS)
    trade = p.close("K", 120.0, TS, qty=65)  # close one tranche
    assert trade.qty == 65
    assert trade.pnl_gross == pytest.approx((120 - 105) * 65)
    # the other 65 lots remain, cost basis untouched
    assert "K" in p.positions
    assert p.positions["K"].qty == 65
    assert p.positions["K"].avg_price == pytest.approx(105.0)


def test_partial_close_of_short_tranche():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=-50, price=200.0, ts=TS)
    p.open(instrument_key="K", symbol="S", qty=-50, price=180.0, ts=TS)  # avg 190, -100
    trade = p.close("K", 150.0, TS, qty=50)  # buy back half
    assert trade.qty == -50
    assert trade.pnl_gross == pytest.approx((150 - 190) * -50)  # profit on the short
    assert p.positions["K"].qty == -50


def test_qty_at_or_above_size_closes_everything():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    p.close("K", 120.0, TS, qty=999)  # more than open size -> full close
    assert "K" not in p.positions


def test_qty_none_is_full_close_backcompat():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    trade = p.close("K", 120.0, TS)  # no qty -> unchanged behaviour
    assert trade.qty == 65
    assert "K" not in p.positions


def test_cash_conserved_across_partial_then_full_close():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=130, price=100.0, ts=TS)
    p.close("K", 100.0, TS, qty=65)
    p.close("K", 100.0, TS)  # close the rest at the same price
    # flat, and — since every contract exited at its entry price — the only thing
    # that left the account is transaction costs. Premium is fully conserved.
    assert p.positions == {}
    assert p.cash == pytest.approx(1_000_000.0 - p.total_costs)
    assert len(p.closed_trades) == 2
