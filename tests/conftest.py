"""Shared fixtures: a synthetic single-instrument market for engine tests."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest

IST = ZoneInfo("Asia/Kolkata")


def bar_frame(rows: list[tuple[datetime, float]]) -> pl.DataFrame:
    """rows: [(timestamp, price)] -> OHLCV frame with O=H=L=C=price."""
    return pl.DataFrame(
        {
            "timestamp": [r[0] for r in rows],
            "open": [float(r[1]) for r in rows],
            "high": [float(r[1]) for r in rows],
            "low": [float(r[1]) for r in rows],
            "close": [float(r[1]) for r in rows],
            "volume": [0] * len(rows),
            "oi": [0] * len(rows),
        }
    )


def minute_day(d: date, price: float = 25000.0, skip_hhmm: tuple[str, ...] = ()) -> list:
    """A full 09:15-15:29 day of 1-min bars at a constant price."""
    rows = []
    for hm in range(9 * 60 + 15, 15 * 60 + 30):
        hhmm = f"{hm // 60:02d}:{hm % 60:02d}"
        if hhmm in skip_hhmm:
            continue
        rows.append((datetime(d.year, d.month, d.day, hm // 60, hm % 60, tzinfo=IST), price))
    return rows


class FakeContract:
    def __init__(self, key="OPT1", strike=25000, option_type="CE", expiry=None):
        self.instrument_key = key
        self.strike = strike
        self.option_type = option_type
        self.expiry = expiry


class FakeResolved:
    def __init__(self, contract):
        self.contract = contract
        self.adjusted = False


class FakeResolver:
    underlying_key = "NSE_INDEX|Nifty 50"
    atm_step = 50

    def __init__(self, expiry: date):
        self._expiry = expiry

    def nearest_expiry(self, d, kind="weekly"):
        return self._expiry

    def atm_strike(self, spot):
        return int(round(spot / self.atm_step) * self.atm_step)

    def resolve(self, expiry, strike, option_type, on_date=None):
        return FakeResolved(FakeContract(expiry=self._expiry))


class FakeReader:
    """spot_frames/option_frames: dict[date, DataFrame]."""

    def __init__(self, spot_frames: dict, option_frames: dict):
        self._spot = spot_frames
        self._opt = option_frames

    def spot_bars(self, key, d, interval="1minute"):
        return self._spot.get(d, bar_frame([]))

    def option_bars(self, key, d, interval="1minute"):
        return self._opt.get(d, bar_frame([]))


@pytest.fixture
def ist():
    return IST
