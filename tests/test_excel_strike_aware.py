"""Strike-aware offline source: honor strike_offset when a chain is present,
fall back to the nearest strike when it isn't.

Builds a tiny two-day workbook (one chain day, one ATM-only day) so the whole
read -> resolve -> option_bars path is exercised without the bundled 18 MB file.
"""
from datetime import date

import pytest

openpyxl = pytest.importorskip("openpyxl")

from bhav.data.excel_source import (  # noqa: E402
    ExcelDataReader,
    ExcelDataSource,
    ExcelInstrumentResolver,
)

CHAIN_DAY = date(2026, 6, 1)
ATM_DAY = date(2026, 6, 2)
EXPIRY = date(2026, 6, 4)


def _mini_workbook(path):
    """One chain day (strikes 23600/23650/23700) + one ATM-only day (24000)."""
    wb = openpyxl.Workbook()
    ws_spot = wb.active
    ws_spot.title = "Spot_1min"
    ws_spot.append(["Date", "Time", "Open", "High", "Low", "Close", "Volume"])
    for d, px in ((CHAIN_DAY, 23650), (ATM_DAY, 24000)):
        ws_spot.append([d.isoformat(), "09:15:00", px, px, px, px, 0])

    ws = wb.create_sheet("ATM_Options_1min")
    ws.append(["Date", "Time", "Timestamp", "Strike", "Type", "Expiry",
               "Open", "High", "Low", "Close", "Volume", "OI"])

    def row(d, strike, otype, price):
        ts = f"{d.isoformat()}T09:15:00+05:30"
        ws.append([d.isoformat(), "09:15:00", ts, strike, otype, EXPIRY.isoformat(),
                   price, price, price, price, 100, 1000])

    for strike in (23600, 23650, 23700):        # chain day: 3 strikes each side
        row(CHAIN_DAY, strike, "CE", 120.0)
        row(CHAIN_DAY, strike, "PE", 110.0)
    row(ATM_DAY, 24000, "CE", 130.0)            # ATM-only day: single strike
    row(ATM_DAY, 24000, "PE", 125.0)
    wb.save(path)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "mini.xlsx"
    _mini_workbook(path)
    return ExcelDataSource(path)


def test_available_strikes(source):
    assert source.available_strikes(CHAIN_DAY, "CE") == [23600, 23650, 23700]
    assert source.available_strikes(ATM_DAY, "CE") == [24000]


def test_exact_strike_resolves(source):
    c = source.contract_for(CHAIN_DAY, "CE", 23700)
    assert c.strike == 23700
    assert c.instrument_key == "EXCEL|CE|23700|2026-06-01"


def test_offsets_are_distinct_keys_on_chain_day(source):
    lo = source.contract_for(CHAIN_DAY, "CE", 23600)
    hi = source.contract_for(CHAIN_DAY, "CE", 23700)
    assert lo.instrument_key != hi.instrument_key


def test_missing_strike_falls_back_to_nearest(source):
    # 23900 has no data; nearest present is 23700
    c = source.contract_for(CHAIN_DAY, "CE", 23900)
    assert c.strike == 23700


def test_atm_only_day_collapses_offsets(source):
    # any requested strike resolves to the single available one
    a = source.contract_for(ATM_DAY, "CE", 24000)
    b = source.contract_for(ATM_DAY, "CE", 24100)
    assert a.instrument_key == b.instrument_key == "EXCEL|CE|24000|2026-06-02"


def test_reader_parses_strike_from_key(source):
    reader = ExcelDataReader(source)
    bars = reader.option_bars("EXCEL|CE|23600|2026-06-01", CHAIN_DAY)
    assert bars.height == 1
    assert bars["close"][0] == pytest.approx(120.0)


def test_reader_tolerates_legacy_keyless_form(source):
    # old "EXCEL|{type}|{day}" form (no strike) -> first available strike
    reader = ExcelDataReader(source)
    bars = reader.option_bars("EXCEL|CE|2026-06-01", CHAIN_DAY)
    assert bars.height == 3  # all three strikes for that side/day


def test_resolver_sets_adjusted_flag(source):
    r = ExcelInstrumentResolver(source)
    exact = r.resolve(EXPIRY, 23650, "CE", on_date=CHAIN_DAY)
    assert exact.adjusted is False
    approx = r.resolve(EXPIRY, 23900, "CE", on_date=CHAIN_DAY)
    assert approx.adjusted is True
    assert approx.contract.strike == 23700
