"""Auto-roll of the front-month future for futures-basis ATM.

Covers the expiry-millis parsing, the roll boundary (before / on / after expiry),
the master-filtering, local caching, and that the engine drives a per-day rolled
key into the ATM reference.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from bhav.data.futures import (
    FuturesResolutionError,
    FuturesRoll,
    InstrumentMaster,
    _expiry_to_date,
)
from bhav.data.underlyings import futures_identity
from bhav.engine.bar_engine import BarEngine, EngineConfig
from bhav.engine.strategy import Context, Strategy
from tests.conftest import FakeContract, FakeResolved, bar_frame

IST = ZoneInfo("Asia/Kolkata")


# --- expiry parsing ---------------------------------------------------------

def test_expiry_millis_to_ist_date():
    # 28 JUL 2026 close, from the real NIFTY future row
    assert _expiry_to_date(1785263399000) == date(2026, 7, 28)


def test_expiry_accepts_iso_string_and_none():
    assert _expiry_to_date("2026-07-28") == date(2026, 7, 28)
    assert _expiry_to_date(None) is None
    assert _expiry_to_date("garbage") is None


# --- roll boundary ----------------------------------------------------------

def _roll():
    return FuturesRoll([
        (date(2026, 7, 28), "NSE_FO|JUL"),
        (date(2026, 8, 25), "NSE_FO|AUG"),
        (date(2026, 9, 29), "NSE_FO|SEP"),
    ])


def test_front_month_before_expiry():
    assert _roll().front_month(date(2026, 7, 6)) == "NSE_FO|JUL"


def test_front_month_on_expiry_day_still_uses_that_contract():
    # expires at day's close, so intraday it is still the front month
    assert _roll().front_month(date(2026, 7, 28)) == "NSE_FO|JUL"


def test_front_month_rolls_after_expiry():
    assert _roll().front_month(date(2026, 7, 29)) == "NSE_FO|AUG"
    assert _roll().front_month(date(2026, 8, 26)) == "NSE_FO|SEP"


def test_front_month_none_past_last_contract():
    assert _roll().front_month(date(2026, 12, 1)) is None


# --- master filtering -------------------------------------------------------

class _StubMaster:
    """Stands in for InstrumentMaster.load without any network."""

    def __init__(self, rows):
        self._rows = rows

    def load(self, exchange):
        assert exchange == "NSE"
        return self._rows


def test_from_master_filters_by_name_segment_and_type():
    rows = [
        {"instrument_type": "FUT", "segment": "NSE_FO", "name": "NIFTY",
         "instrument_key": "NSE_FO|JUL", "expiry": 1785263399000},
        {"instrument_type": "FUT", "segment": "NSE_FO", "name": "BANKNIFTY",
         "instrument_key": "NSE_FO|BNF", "expiry": 1785263399000},   # wrong name
        {"instrument_type": "OPTIDX", "segment": "NSE_FO", "name": "NIFTY",
         "instrument_key": "NSE_FO|OPT", "expiry": 1785263399000},   # wrong type
        {"instrument_type": "FUT", "segment": "NSE_EQ", "name": "NIFTY",
         "instrument_key": "NSE_EQ|X", "expiry": 1785263399000},     # wrong segment
    ]
    roll = FuturesRoll.from_master(_StubMaster(rows), "NIFTY", "NSE_FO")
    assert roll.expiries() == [date(2026, 7, 28)]
    assert roll.front_month(date(2026, 7, 1)) == "NSE_FO|JUL"


def test_from_master_raises_when_no_contracts():
    with pytest.raises(FuturesResolutionError, match="no NIFTY futures"):
        FuturesRoll.from_master(_StubMaster([]), "NIFTY", "NSE_FO")


# --- local caching (no network) --------------------------------------------

def test_master_uses_fresh_cache_without_network(tmp_path):
    m = InstrumentMaster(cache_dir=tmp_path)
    # pre-seed a cache file; if load() hits the network this test would need one
    (m.dir / "NSE.json").write_text('[{"a": 1}]', encoding="utf-8")
    assert m.load("NSE") == [{"a": 1}]


# --- mapping table ----------------------------------------------------------

def test_underlying_futures_identity():
    assert futures_identity("NSE_INDEX|Nifty 50") == ("NIFTY", "NSE_FO")
    assert futures_identity("BSE_INDEX|SENSEX") == ("SENSEX", "BSE_FO")
    assert futures_identity("NSE_INDEX|Unknown thing") is None


# --- engine integration -----------------------------------------------------

class BuyAtmCE(Strategy):
    name = "buy_atm_ce"

    def on_bar(self, ctx: Context) -> None:
        hhmm = f"{ctx.bar.timestamp.hour:02d}:{ctx.bar.timestamp.minute:02d}"
        if hhmm == "09:16" and not ctx.portfolio.positions and not ctx.is_warmup:
            ctx.buy_option(option_type="CE")


class _RollReader:
    """Distinct futures frames per key so we can see which one the engine used."""

    def __init__(self, spot, fut_by_key, opt):
        self._spot = spot
        self._fut = fut_by_key
        self._opt = opt

    def spot_bars(self, key, d, interval="1minute"):
        if key in self._fut:
            return self._fut[key]
        return self._spot

    def option_bars(self, key, d, interval="1minute"):
        return self._opt


class _CapturingResolver:
    underlying_key = "NSE_INDEX|Nifty 50"
    atm_step = 50
    last_strike = None

    def __init__(self, expiry):
        self._expiry = expiry

    def nearest_expiry(self, d, kind="weekly"):
        return self._expiry

    def atm_strike(self, spot):
        return int(round(spot / self.atm_step) * self.atm_step)

    def resolve(self, expiry, strike, option_type, on_date=None):
        _CapturingResolver.last_strike = strike
        return FakeResolved(FakeContract(expiry=self._expiry))


class _FixedRoll:
    def __init__(self, key):
        self.key = key

    def front_month(self, on_date):
        return self.key


def test_engine_uses_rolled_front_month_key():
    day = date(2026, 7, 6)
    times = [datetime(2026, 7, 6, 9, m, tzinfo=IST) for m in range(15, 20)]
    spot = bar_frame([(t, 24_341) for t in times])      # spot ATM -> 24350
    fut = bar_frame([(t, 24_410) for t in times])       # future ATM -> 24400
    opt = bar_frame([(t, 100.0) for t in times])

    cfg = EngineConfig(
        underlying_key="NSE_INDEX|Nifty 50",
        start=day,
        end=day,
        starting_capital=1_000_000,
        lot_size=65,
        atm_reference="futures",
        futures_auto=True,
    )
    reader = _RollReader(spot, {"NSE_FO|JUL": fut}, opt)
    engine = BarEngine(cfg, reader, _CapturingResolver(day), futures_roll=_FixedRoll("NSE_FO|JUL"))
    engine.run(BuyAtmCE())
    # ATM came off the future (24400), not spot (24350)
    assert engine.resolver.last_strike == 24_400


def test_engine_futures_without_key_or_roll_raises():
    cfg = EngineConfig(
        underlying_key="NSE_INDEX|Nifty 50", start=date(2026, 7, 6), end=date(2026, 7, 6),
        atm_reference="futures", futures_auto=True,
    )
    reader = _RollReader(bar_frame([]), {}, bar_frame([]))
    with pytest.raises(ValueError, match="futures_roll"):
        BarEngine(cfg, reader, _CapturingResolver(date(2026, 7, 6)))
