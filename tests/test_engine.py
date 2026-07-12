"""Regression tests for BarEngine bugs: MTM curve, day-start/square-off on feed gaps."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import polars as pl

from bhav.data.calendar import NSECalendar
from bhav.engine.bar_engine import BarEngine, EngineConfig
from bhav.engine.strategy import Context, Strategy
from tests.conftest import FakeReader, FakeResolver, bar_frame, minute_day

IST = ZoneInfo("Asia/Kolkata")
D1 = date(2025, 8, 1)
D2 = date(2025, 8, 4)


def make_engine(spot_frames, option_frames, start=D1, end=D1, **cfg_kw):
    cfg = EngineConfig(
        underlying_key="NSE_INDEX|Nifty 50",
        start=start,
        end=end,
        starting_capital=100_000,
        lot_size=65,
        calendar=NSECalendar(),
        **cfg_kw,
    )
    return BarEngine(cfg, FakeReader(spot_frames, option_frames), FakeResolver(end))


class BuyOnceHold(Strategy):
    name = "buy_once_hold"

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if hhmm == "09:16" and not ctx.portfolio.positions and not ctx.is_warmup:
            ctx.buy_option(option_type="CE")


def test_equity_curve_marks_open_positions_to_market():
    spot = bar_frame([(datetime(2025, 8, 1, 9, m, tzinfo=IST), 25000) for m in range(15, 21)])
    opt = bar_frame(
        [(datetime(2025, 8, 1, 9, m, tzinfo=IST), p) for m, p in
         [(15, 100), (16, 100), (17, 10), (18, 10), (19, 10), (20, 50)]]
    )
    eng = make_engine({D1: spot}, {D1: opt})
    pf = eng.run(BuyOnceHold())
    # the crash to 10 must be visible in the curve while the trade is open
    assert min(eq for _, eq in pf.equity_curve) < 95_000


def test_day_start_fires_without_0915_bar():
    calls = []

    class S(Strategy):
        name = "s"

        def on_day_start(self, ctx):
            calls.append(ctx.date)

        def on_bar(self, ctx):
            pass

    spot = bar_frame(minute_day(D1, skip_hhmm=("09:15",)))
    eng = make_engine({D1: spot}, {D1: spot})
    eng.run(S())
    assert calls == [D1]


def test_square_off_fires_without_1515_bar_and_position_reaches_trades():
    spot = bar_frame(minute_day(D1, skip_hhmm=("15:15",)))
    opt = bar_frame(minute_day(D1, price=100.0, skip_hhmm=("15:15",)))
    eng = make_engine({D1: spot}, {D1: opt})
    pf = eng.run(BuyOnceHold())
    assert pf.positions == {}
    assert len(pf.closed_trades) == 1
    assert pf.closed_trades[0].reason == "eod_square_off"


def test_leftover_position_flattened_even_if_feed_ends_before_square_off():
    # feed dies at 11:00 - no bar at or after 15:15 at all
    rows = [r for r in minute_day(D1) if r[0].hour < 11]
    opt_rows = [(ts, 100.0) for ts, _ in rows]
    eng = make_engine({D1: bar_frame(rows)}, {D1: bar_frame(opt_rows)})
    pf = eng.run(BuyOnceHold())
    assert pf.positions == {}
    assert len(pf.closed_trades) == 1


def test_no_new_orders_after_square_off():
    class LateBuyer(Strategy):
        name = "late"

        def on_bar(self, ctx):
            hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
            if hhmm == "15:20" and not ctx.portfolio.positions:
                ctx.buy_option(option_type="CE")

    spot = bar_frame(minute_day(D1))
    opt = bar_frame(minute_day(D1, price=100.0))
    eng = make_engine({D1: spot}, {D1: opt})
    pf = eng.run(LateBuyer())
    assert pf.positions == {}
    assert pf.closed_trades == []


def test_on_bar_still_fires_after_square_off_for_history_building():
    seen = []

    class Recorder(Strategy):
        name = "rec"

        def on_bar(self, ctx):
            seen.append(f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}")

    spot = bar_frame(minute_day(D1))
    eng = make_engine({D1: spot}, {D1: spot})
    eng.run(Recorder())
    assert "15:29" in seen  # late bars still delivered to the strategy


def test_buy_rejected_when_premium_exceeds_cash():
    spot = bar_frame(minute_day(D1, price=25000))
    opt = bar_frame(minute_day(D1, price=100_000))  # absurd premium > capital
    eng = make_engine({D1: spot}, {D1: opt})
    pf = eng.run(BuyOnceHold())
    assert pf.positions == {}
    assert pf.closed_trades == []
    assert pf.cash == 100_000
