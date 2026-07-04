"""DataReader: strategies read from here. Hides cache-vs-API from user code."""
from __future__ import annotations

from datetime import date

import polars as pl

from bhav.data.cache import ParquetCache
from bhav.data.upstox_client import UpstoxClient


class DataReader:
    def __init__(self, client: UpstoxClient, cache: ParquetCache) -> None:
        self.client = client
        self.cache = cache

    def spot_bars(
        self, instrument_key: str, d: date, interval: str = "1minute"
    ) -> pl.DataFrame:
        if self.cache.has(instrument_key, interval, d):
            return self.cache.read(instrument_key, interval, d)
        raw = self.client.get_index_candles(instrument_key, interval, d, d)
        df = self.cache.candles_to_frame(raw)
        self.cache.write(instrument_key, interval, d, df)
        return df

    def option_bars(
        self, expired_key: str, d: date, interval: str = "1minute"
    ) -> pl.DataFrame:
        if self.cache.has(expired_key, interval, d):
            return self.cache.read(expired_key, interval, d)
        raw = self.client.get_expired_option_candles(expired_key, interval, d, d)
        df = self.cache.candles_to_frame(raw)
        self.cache.write(expired_key, interval, d, df)
        return df
