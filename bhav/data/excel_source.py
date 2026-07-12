"""Offline Excel data source.

Lets anyone run a backtest without Upstox API access, using a bundled
1-year NIFTY dataset (`sample_data/nifty_1y_1min.xlsx`): one sheet of
1-minute spot candles, one sheet of 1-minute ATM option candles.

Limitations vs live Upstox data (this is a fixed historical snapshot,
not a full option chain):
    - NIFTY 50 only.
    - Only the ATM strike (CE + PE) for that day's nearest weekly expiry
      is recorded. `strike_offset` in `ctx.buy_option()` is ignored; you
      always get the real ATM contract for that day, whatever it is.
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

    def option_bars(self, d: date, option_type: str) -> pl.DataFrame:
        """Ignores strike: only one strike (the real ATM) exists per day per side."""
        return (
            self.options.filter((pl.col("day") == d) & (pl.col("option_type") == option_type))
            .select(_BAR_COLUMNS)
        )

    def contract_for(self, d: date, option_type: str) -> OptionContract | None:
        row = self.options.filter(
            (pl.col("day") == d) & (pl.col("option_type") == option_type)
        ).head(1)
        if row.is_empty():
            return None
        return OptionContract(
            instrument_key=f"EXCEL|{option_type}|{d.isoformat()}",
            strike=int(row["strike"][0]),
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
        # instrument_key format: "EXCEL|{option_type}|{day}" (see ExcelDataSource.contract_for)
        option_type = instrument_key.split("|")[1]
        return self.source.option_bars(d, option_type)


class ExcelInstrumentResolver:
    """Drop-in replacement for `bhav.data.instruments.InstrumentResolver` in offline mode.

    `strike` and `expiry` arguments to `resolve()` are accepted for interface
    compatibility but not honored precisely: the dataset only ever has the
    real ATM strike for the day, so that's always what you get.
    """

    underlying_key = "NSE_INDEX|Nifty 50"
    atm_step = 50

    def __init__(self, source: ExcelDataSource) -> None:
        self.source = source
        self._on_date: date | None = None

    def expiries(self) -> list[date]:
        return self.source.expiries()

    def nearest_expiry(self, on_date: date, kind: str = "weekly") -> date | None:
        self._on_date = on_date
        candidates = [e for e in self.expiries() if e >= on_date]
        return min(candidates) if candidates else None

    def atm_strike(self, spot: float) -> int:
        return int(round(spot / self.atm_step) * self.atm_step)

    def resolve(self, expiry: date, strike: int, option_type: str) -> ResolvedOption | None:
        on_date = self._on_date or expiry
        contract = self.source.contract_for(on_date, option_type)
        if contract is None:
            return None
        return ResolvedOption(contract=contract, adjusted=contract.strike != strike)
