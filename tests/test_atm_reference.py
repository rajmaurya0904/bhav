"""ATM reference price: spot by default, futures when configured.

NIFTY options price off the future, so ATM chosen off raw spot is biased by the
basis. These tests pin the plumbing: the strike is picked from the futures price
when one is supplied, and falls back to spot otherwise.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from bhav.engine.bar_engine import BarEngine, EngineConfig
from bhav.engine.strategy import Bar, Context, Strategy
from tests.conftest import FakeReader, FakeResolver, bar_frame

IST = ZoneInfo("Asia/Kolkata")
D1 = date(2025, 8, 1)


def _ctx(spot_close, atm_ref=None):
    ts = datetime(2025, 8, 1, 9, 20, tzinfo=IST)
    bar = Bar(ts, spot_close, spot_close, spot_close, spot_close, 0)
    return Context(
        current_date=D1,
        current_bar=bar,
        reader=FakeReader({}, {}),
        resolver=FakeResolver(D1),
        portfolio=None,
        lot_size=65,
        atm_ref_price=atm_ref,
    )


def test_reference_defaults_to_spot():
    ctx = _ctx(25_012.0)
    assert ctx.atm_reference_price() == pytest.approx(25_012.0)


def test_reference_uses_futures_when_supplied():
    # future trades ~80 pts over spot; ATM must round the future, not spot
    ctx = _ctx(25_012.0, atm_ref=25_090.0)
    assert ctx.atm_reference_price() == pytest.approx(25_090.0)
    # FakeResolver.atm_strike rounds to step 50: spot->25000, future->25100
    assert ctx.resolver.atm_strike(ctx.spot()) == 25_000
    assert ctx.resolver.atm_strike(ctx.atm_reference_price()) == 25_100


def test_engine_config_futures_requires_key():
    with pytest.raises(ValueError, match="futures_key"):
        EngineConfig(underlying_key="NSE_INDEX|Nifty 50", start=D1, end=D1, atm_reference="futures")


def test_engine_config_rejects_bad_reference():
    with pytest.raises(ValueError, match="atm_reference"):
        EngineConfig(underlying_key="NSE_INDEX|Nifty 50", start=D1, end=D1, atm_reference="wat")


class BuyAtmCE(Strategy):
    name = "buy_atm_ce"

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if hhmm == "09:16" and not ctx.portfolio.positions and not ctx.is_warmup:
            ctx.buy_option(option_type="CE")


def test_engine_picks_strike_from_futures_price():
    # spot sits at 25010 (ATM 25000); future at 25140 (ATM 25150)
    times = [datetime(2025, 8, 1, 9, m, tzinfo=IST) for m in range(15, 20)]
    spot = bar_frame([(t, 25_010) for t in times])
    fut = bar_frame([(t, 25_140) for t in times])
    opt = bar_frame([(t, 100.0) for t in times])

    cfg = EngineConfig(
        underlying_key="NSE_INDEX|Nifty 50",
        start=D1,
        end=D1,
        starting_capital=1_000_000,
        lot_size=65,
        atm_reference="futures",
        futures_key="NSE_FO|FUTIDX_NIFTY",
    )
    # FakeReader.spot_bars returns the same frame for any key; give it both via a
    # keyed reader so spot vs futures differ.
    reader = _KeyedReader({"NSE_INDEX|Nifty 50": spot, "NSE_FO|FUTIDX_NIFTY": fut}, {"OPT1": opt})
    engine = BarEngine(cfg, reader, _StrikeCapturingResolver(D1))
    engine.run(BuyAtmCE())
    # the resolver recorded the strike it was asked to resolve
    assert engine.resolver.last_strike == 25_150


class _KeyedReader:
    def __init__(self, spot_by_key, option_frames):
        self._spot_by_key = spot_by_key
        self._opt = option_frames

    def spot_bars(self, key, d, interval="1minute"):
        return self._spot_by_key.get(key, bar_frame([]))

    def option_bars(self, key, d, interval="1minute"):
        return self._opt.get(key, bar_frame([]))


class _StrikeCapturingResolver(FakeResolver):
    last_strike = None

    def resolve(self, expiry, strike, option_type, on_date=None):
        _StrikeCapturingResolver.last_strike = strike
        return super().resolve(expiry, strike, option_type, on_date)
