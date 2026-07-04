"""Parquet-backed local cache for Upstox candles. Cache-first, API-fallback."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import polars as pl

DEFAULT_CACHE_DIR = Path.home() / ".backtester" / "cache"
CANDLE_SCHEMA = {
    "timestamp": pl.Datetime(time_zone="Asia/Kolkata"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "oi": pl.Int64,
}


def _safe_key(instrument_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", instrument_key)


class ParquetCache:
    """Cache key = (instrument_key, interval, date). One Parquet per (key, interval, day)."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else DEFAULT_CACHE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, instrument_key: str, interval: str, d: date) -> Path:
        h = hashlib.sha1(instrument_key.encode()).hexdigest()[:8]
        safe = _safe_key(instrument_key)[:60]
        return (
            self.root
            / f"{safe}_{h}"
            / interval
            / f"{d:%Y-%m-%d}.parquet"
        )

    def has(self, instrument_key: str, interval: str, d: date) -> bool:
        return self.path_for(instrument_key, interval, d).exists()

    def read(self, instrument_key: str, interval: str, d: date) -> pl.DataFrame:
        return pl.read_parquet(self.path_for(instrument_key, interval, d))

    def write(
        self, instrument_key: str, interval: str, d: date, df: pl.DataFrame
    ) -> None:
        path = self.path_for(instrument_key, interval, d)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)

    @staticmethod
    def candles_to_frame(raw: list[list]) -> pl.DataFrame:
        """Upstox candles: [timestamp, open, high, low, close, volume, oi?]."""
        if not raw:
            return pl.DataFrame(schema=CANDLE_SCHEMA)
        rows = []
        for c in raw:
            ts, o, h, l, cl, vol = c[0], c[1], c[2], c[3], c[4], c[5]
            oi = int(c[6]) if len(c) > 6 else 0
            rows.append({
                "timestamp": ts,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(cl),
                "volume": int(vol),
                "oi": int(oi),
            })
        df = pl.DataFrame(rows)
        return (
            df.with_columns(
                pl.col("timestamp").str.to_datetime(time_zone="Asia/Kolkata")
            )
            .sort("timestamp")
            .unique(subset=["timestamp"], keep="last")
        )
