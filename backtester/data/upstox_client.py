"""Upstox v2 historical-data client. Chunked, retried, rate-limited."""
from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

BASE_URL = "https://api.upstox.com/v2"
DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
RATE_LIMIT_DELAY = 0.05


class UpstoxError(Exception):
    """Raised on any non-recoverable Upstox failure."""


class TokenExpiredError(UpstoxError):
    """Upstox tokens expire daily around 03:30 IST. Fail loudly."""


@dataclass(frozen=True)
class OptionContract:
    instrument_key: str
    strike: int
    option_type: str
    expiry: date


class UpstoxClient:
    """Thin wrapper over the four historical endpoints used by the engine.

    Endpoints wrapped:
        1. GET /v2/historical-candle/{key}/{interval}/{from}/{to}
        2. GET /v2/expired-instruments/expiries?instrument_key=...
        3. GET /v2/expired-instruments/option/contract?instrument_key=...&expiry_date=...
        4. GET /v2/expired-instruments/historical-candle/{expired_key}/{interval}/{from}/{to}
    """

    def __init__(
        self,
        token: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF,
    ) -> None:
        if not token or token == "PASTE_YOUR_TOKEN_HERE":
            raise UpstoxError("Missing Upstox access token")
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        self._retries = retries
        self._backoff = backoff

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> UpstoxClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                time.sleep(RATE_LIMIT_DELAY)
                r = self._client.get(path, params=params)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 401:
                    raise TokenExpiredError(
                        "Upstox 401: access token expired or invalid. "
                        "Tokens expire daily around 03:30 IST. Refresh and retry."
                    )
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(self._backoff * (2**attempt))
                    continue
                raise UpstoxError(f"HTTP {r.status_code} on {path}: {r.text[:200]}")
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_exc = e
                time.sleep(self._backoff * (2**attempt))
        raise UpstoxError(f"Failed after {self._retries} retries: {last_exc}") from last_exc

    def get_index_candles(
        self, instrument_key: str, interval: str, from_date: date, to_date: date
    ) -> list[list]:
        """Endpoint 1: live-instrument historical candles (spot indices, futures)."""
        key = urllib.parse.quote(instrument_key, safe="")
        path = f"/historical-candle/{key}/{interval}/{to_date:%Y-%m-%d}/{from_date:%Y-%m-%d}"
        data = self._get(path)
        return data.get("data", {}).get("candles", []) or []

    def get_expired_expiries(self, underlying_key: str) -> list[date]:
        """Endpoint 2: list of past expiries for an underlying."""
        data = self._get(
            "/expired-instruments/expiries", params={"instrument_key": underlying_key}
        )
        raw = data.get("data", []) or []
        return sorted({date.fromisoformat(x) for x in raw if x})

    def get_expired_contracts(
        self, underlying_key: str, expiry: date
    ) -> list[OptionContract]:
        """Endpoint 3: full option chain (all strikes, CE + PE) for one expired expiry."""
        data = self._get(
            "/expired-instruments/option/contract",
            params={
                "instrument_key": underlying_key,
                "expiry_date": expiry.isoformat(),
            },
        )
        raw = data.get("data", []) or []
        out: list[OptionContract] = []
        for c in raw:
            strike = c.get("strike_price") or c.get("strikePrice")
            otype = c.get("instrument_type") or c.get("instrumentType")
            ikey = c.get("instrument_key") or c.get("instrumentKey")
            if strike is None or otype not in ("CE", "PE") or not ikey:
                continue
            out.append(
                OptionContract(
                    instrument_key=ikey,
                    strike=int(float(strike)),
                    option_type=otype,
                    expiry=expiry,
                )
            )
        return out

    def get_expired_option_candles(
        self, expired_key: str, interval: str, from_date: date, to_date: date
    ) -> list[list]:
        """Endpoint 4: intraday candles for an expired option contract.

        Upstox caps 1-minute range per call. Auto-chunk into 30-day windows.
        """
        if interval != "1minute":
            return self._fetch_expired_range(expired_key, interval, from_date, to_date)
        out: list[list] = []
        cursor = from_date
        chunk_days = 30
        while cursor <= to_date:
            chunk_end = min(cursor + timedelta(days=chunk_days - 1), to_date)
            out.extend(self._fetch_expired_range(expired_key, interval, cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)
        return out

    def _fetch_expired_range(
        self, expired_key: str, interval: str, from_date: date, to_date: date
    ) -> list[list]:
        key = urllib.parse.quote(expired_key, safe="")
        path = (
            f"/expired-instruments/historical-candle/{key}/{interval}/"
            f"{to_date:%Y-%m-%d}/{from_date:%Y-%m-%d}"
        )
        data = self._get(path)
        return data.get("data", {}).get("candles", []) or []
