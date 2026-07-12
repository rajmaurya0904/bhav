"""Regression tests for Portfolio accounting bugs found in the systematic audit."""
from datetime import datetime

import pytest

from bhav.engine.costs import CostModel, IndianCostModel
from bhav.engine.portfolio import OppositeSideError, Portfolio


class NoFrictionModel(IndianCostModel):
    """Zero slippage so price arithmetic in tests is exact."""

    slippage_ticks: float = 0.0

    def __init__(self):
        super().__init__(slippage_ticks=0.0)


TS = datetime(2025, 8, 1, 9, 30)


def _pf(capital=100_000.0, cost_model=None):
    return Portfolio(starting_capital=capital, cost_model=cost_model or NoFrictionModel())


def test_same_key_open_averages_instead_of_overwriting():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    p.open(instrument_key="K", symbol="S", qty=65, price=110.0, ts=TS)
    pos = p.positions["K"]
    assert pos.qty == 130
    assert pos.avg_price == pytest.approx(105.0)
    trade = p.close("K", 120.0, TS)
    assert trade.pnl_gross == pytest.approx((120 - 105) * 130)


def test_same_key_cash_and_equity_consistent():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    p.open(instrument_key="K", symbol="S", qty=65, price=110.0, ts=TS)
    p.close("K", 120.0, TS)
    total_costs = p.total_costs
    # all premium paid must come back through the close; only costs are lost
    expected_cash = 100_000 - 65 * 100 - 65 * 110 + 130 * 120 - total_costs
    assert p.cash == pytest.approx(expected_cash)


def test_opposite_side_open_rejected():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    with pytest.raises(OppositeSideError):
        p.open(instrument_key="K", symbol="S", qty=-65, price=100.0, ts=TS)


def test_mark_uses_current_prices():
    p = _pf()
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    eq = p.mark(TS, {"K": 10.0})  # premium crashed
    assert eq == pytest.approx(100_000 - 65 * 100 - p.total_costs + 65 * 10)
    assert eq < 95_000


def test_exposure_curve_tracks_positions():
    p = _pf()
    p.mark(TS, {})
    p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    p.mark(TS, {"K": 100.0})
    p.close("K", 100.0, TS)
    p.mark(TS, {})
    assert p.exposure_curve == [False, True, False]


def test_slippage_applied_against_trader():
    p = _pf(cost_model=IndianCostModel())  # default 1 tick = 0.05
    pos = p.open(instrument_key="K", symbol="S", qty=65, price=100.0, ts=TS)
    assert pos.avg_price == pytest.approx(100.05)  # buy fills higher
    trade = p.close("K", 100.0, TS)
    assert trade.exit_price == pytest.approx(99.95)  # sell fills lower


def test_short_close_slippage_direction():
    p = _pf(cost_model=IndianCostModel())
    pos = p.open(instrument_key="K", symbol="S", qty=-65, price=100.0, ts=TS)
    assert pos.avg_price == pytest.approx(99.95)  # sell to open fills lower
    trade = p.close("K", 100.0, TS)
    assert trade.exit_price == pytest.approx(100.05)  # buy to close fills higher


def test_fill_price_never_below_tick():
    m = IndianCostModel()
    assert m.fill_price(0.05, is_buy=False) == pytest.approx(0.05)
