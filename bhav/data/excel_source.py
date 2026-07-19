"""Offline Excel data source.

Lets anyone run a backtest without Upstox API access, using a bundled
1-year NIFTY dataset (`sample_data/nifty_1y_1min.xlsx`): one sheet of
1-minute spot candles, one sheet of 1-minute ATM option candles.

The workbook may carry either a single ATM strike per day (the original
snapshot) or a small chain of strikes around the ATM (the extended snapshot,
built by `scripts/build_sample_data.py`). This source honors `strike_offset`
whenever the requested strike exists in the data, and otherwise falls back to
the nearest strike that does — so single-leg strategies keep working on
ATM-only days, and spreads (verticals, condors) become testable on the days a
chain is present.

Limitations vs live Upstox data (this is a fixed historical snapshot):
    - NIFTY 50 only.
    - Strike coverage is whatever the workbook holds for each day. On ATM-only
      days every `strike_offset` collapses to the ATM contract (so same-side
      spread legs share one key); on chain days offsets resolve to distinct
      strikes. A requested strike with no data falls back to the nearest one.
    - Covers the dates present in the workbook only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from bhav.data.upstox_client import OptionContract

IST = "Asia/Kolkata"

DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parents[2] / "sample_data" / "nifty_1y_1min.xlsx"
)

_BAR_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


@dataclass(frozen=True)
class ResolvedOption:
    contract: OptionContract
    adjusted: bool


class ExcelDataSource:
    """Loads both sheets once; reader/resolver below just slice these frames."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_EXCEL_PATH
        if not self.path.exists():
            raise FileNotFoundError(
                f"Excel data source not found at {self.path}. "
                "Pass an explicit path or restore sample_data/nifty_1y_1min.xlsx."
            )

        spot_raw = pl.read_excel(self.path, sheet_name="Spot_1min")
        opt_raw = pl.read_excel(self.path, sheet_name="ATM_Options_1min")

        self.spot = (
            spot_raw.with_columns(
                (pl.col("Date") + " " + pl.col("Time"))
                .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
                .dt.replace_time_zone(IST)
                .alias("timestamp")
            )
            .select(
                pl.col("timestamp"),
                pl.col("Open").alias("open"),
                pl.col("High").alias("high"),
                pl.col("Low").alias("low"),
                pl.col("Close").alias("close"),
                pl.col("Volume").cast(pl.Int64).alias("volume"),
                pl.lit(0).cast(pl.Int64).alias("oi"),
            )
            .sort("timestamp")
        )

        self.options = (
            opt_raw.with_columns(
                pl.col("Timestamp")
                .str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%z")
                .dt.convert_time_zone(IST)
                .alias("timestamp"),
                pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d").alias("day"),
                pl.col("Expiry").str.strptime(pl.Date, "%Y-%m-%d").alias("expiry"),
            )
            .select(
                pl.col("timestamp"),
                pl.col("day"),
                pl.col("Strike").cast(pl.Int64).alias("strike"),
                pl.col("Type").alias("option_type"),
                pl.col("expiry"),
                pl.col("Open").alias("open"),
                pl.col("High").alias("high"),
                pl.col("Low").alias("low"),
                pl.col("Close").alias("close"),
                pl.col("Volume").cast(pl.Int64).alias("volume"),
                pl.col("OI").cast(pl.Int64).alias("oi"),
            )
            .sort("timestamp")
        )

    def spot_bars(self, d: date) -> pl.DataFrame:
        return self.spot.filter(pl.col("timestamp").dt.date() == d).select(_BAR_COLUMNS)

    def available_strikes(self, d: date, option_type: str) -> list[int]:
        """Strikes present for this day/side, ascending (usually 1, a chain when extended)."""
        return sorted(
            self.options.filter(
                (pl.col("day") == d) & (pl.col("option_type") == option_type)
            )["strike"]
            .unique()
            .to_list()
        )

    def nearest_strike(self, d: date, option_type: str, target: int) -> int | None:
        strikes = self.available_strikes(d, option_type)
        if not strikes:
            return None
        return min(strikes, key=lambda s: abs(s - target))

    def option_bars(
        self, d: date, option_type: str, strike: int | None = None
    ) -> pl.DataFrame:
        """Candles for one contract. `strike=None` returns the first available strike
        (back-compat); otherwise the exact strike (empty if that strike has no data)."""
        q = self.options.filter(
            (pl.col("day") == d) & (pl.col("option_type") == option_type)
        )
        if strike is not None:
            q = q.filter(pl.col("strike") == strike)
        return q.select(_BAR_COLUMNS)

    def contract_for(
        self, d: date, option_type: str, strike: int | None = None
    ) -> OptionContract | None:
        """Resolve to the requested strike, or the nearest strike that has data.

        `strike=None` means "the ATM-ish default" — the nearest to whatever the
        day's median strike is, which on an ATM-only day is just the ATM.
        """
        strikes = self.available_strikes(d, option_type)
        if not strikes:
            return None
        target = strike if strike is not None else strikes[len(strikes) // 2]
        chosen = min(strikes, key=lambda s: abs(s - target))
        row = self.options.filter(
            (pl.col("day") == d)
            & (pl.col("option_type") == option_type)
            & (pl.col("strike") == chosen)
        ).head(1)
        return OptionContract(
            instrument_key=f"EXCEL|{option_type}|{chosen}|{d.isoformat()}",
            strike=chosen,
            option_type=option_type,
            expiry=row["expiry"][0],
        )

    def expiries(self) -> list[date]:
        return sorted(self.options["expiry"].unique().to_list())


class ExcelDataReader:
    """Drop-in replacement for `bhav.data.reader.DataReader` in offline mode."""

    def __init__(self, source: ExcelDataSource) -> None:
        self.source = source

    def spot_bars(self, instrument_key: str, d: date, interval: str = "1minute") -> pl.DataFrame:
        return self.source.spot_bars(d)

    def option_bars(self, instrument_key: str, d: date, interval: str = "1minute") -> pl.DataFrame:
        # instrument_key format: "EXCEL|{option_type}|{strike}|{day}" (see contract_for).
        # Tolerate the older "EXCEL|{option_type}|{day}" (no strike) form too.
        parts = instrument_key.split("|")
        option_type = parts[1]
        strike = int(parts[2]) if len(parts) >= 4 and parts[2].isdigit() else None
        return self.source.option_bars(d, option_type, strike)


class ExcelInstrumentResolver:
    """Drop-in replacement for `bhav.data.instruments.InstrumentResolver` in offline mode.

    `resolve()` honors the requested strike when the workbook has it, and
    otherwise falls back to the nearest strike present for that day/side. On an
    ATM-only day that is always the ATM contract; on a chain day distinct
    offsets resolve to distinct strikes.
    """

    underlying_key = "NSE_INDEX|Nifty 50"
    atm_step = 50

    def __init__(self, source: ExcelDataSource) -> None:
        self.source = source

    def expiries(self) -> list[date]:
        return self.source.expiries()

    def nearest_expiry(self, on_date: date, kind: str = "weekly") -> date | None:
        candidates = [e for e in self.expiries() if e >= on_date]
        return min(candidates) if candidates else None

    def atm_strike(self, spot: float) -> int:
        return int(round(spot / self.atm_step) * self.atm_step)

    def resolve(
        self, expiry: date, strike: int, option_type: str, on_date: date | None = None
    ) -> ResolvedOption | None:
        contract = self.source.contract_for(on_date or expiry, option_type, strike)
        if contract is None:
            return None
        return ResolvedOption(contract=contract, adjusted=contract.strike != strike)
