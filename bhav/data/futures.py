"""Auto-roll the front-month future for futures-basis ATM selection.

NIFTY options price off the future, not spot, so `--atm-reference futures` picks
the ATM strike from the future's price. That needs the *right* future for each
trading day: futures expire monthly, so a multi-month backtest has to roll from
one contract to the next. Rather than make the user hand-feed a per-expiry
`--futures-key`, this module reads Upstox's public instrument master, finds every
future for the underlying, and returns the front-month (nearest un-expired)
contract active on any given day.

The instrument master is a public asset (no token needed) and is cached locally
so it is downloaded at most once a day.
"""
from __future__ import annotations

import gzip
import json
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from bhav.data.cache import DEFAULT_CACHE_DIR

IST = ZoneInfo("Asia/Kolkata")
MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz"
DEFAULT_MAX_AGE_HOURS = 24.0


class FuturesResolutionError(Exception):
    """Raised when no future can be found for the underlying/date."""


class InstrumentMaster:
    """Downloads + caches Upstox's per-exchange instrument master JSON.

    One file per exchange (``NSE`` / ``BSE``), refreshed at most once a day. The
    master lists every instrument; we only ever pull futures rows out of it.
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        *,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
        timeout: float = 60.0,
    ) -> None:
        root = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.dir = root / "instrument_master"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        self.timeout = timeout

    def _path(self, exchange: str) -> Path:
        return self.dir / f"{exchange}.json"

    def _fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours < self.max_age_hours

    def load(self, exchange: str) -> list[dict]:
        """All instrument dicts for an exchange (``NSE`` or ``BSE``)."""
        path = self._path(exchange)
        if self._fresh(path):
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            r = httpx.get(
                MASTER_URL.format(exchange=exchange),
                timeout=self.timeout,
                follow_redirects=True,
            )
            r.raise_for_status()
            data = json.loads(gzip.decompress(r.content))
        except (httpx.HTTPError, OSError, ValueError) as e:
            # Network hiccup: fall back to a stale cached copy if we have one.
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            raise FuturesResolutionError(
                f"could not download the {exchange} instrument master: {e}"
            ) from e
        path.write_text(json.dumps(data), encoding="utf-8")
        return data


def _expiry_to_date(raw: object) -> date | None:
    """Upstox master stores expiry as epoch milliseconds (IST end-of-day)."""
    if raw is None:
        return None
    try:
        millis = int(raw)
    except (TypeError, ValueError):
        # Some feeds carry an ISO string instead.
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None
    return datetime.fromtimestamp(millis / 1000.0, tz=IST).date()


class FuturesRoll:
    """Front-month future lookup for one underlying, built from the master."""

    def __init__(self, contracts: list[tuple[date, str]]) -> None:
        # (expiry, instrument_key) ascending by expiry.
        self._contracts = sorted(contracts)

    @classmethod
    def from_master(
        cls, master: InstrumentMaster, futures_name: str, segment: str
    ) -> FuturesRoll:
        exchange = segment.split("_", 1)[0]  # "NSE_FO" -> "NSE"
        rows = master.load(exchange)
        contracts: list[tuple[date, str]] = []
        for r in rows:
            if r.get("instrument_type") != "FUT":
                continue
            if r.get("segment") != segment or r.get("name") != futures_name:
                continue
            key = r.get("instrument_key")
            exp = _expiry_to_date(r.get("expiry"))
            if key and exp:
                contracts.append((exp, key))
        if not contracts:
            raise FuturesResolutionError(
                f"no {futures_name} futures found in the {exchange} instrument master"
            )
        return cls(contracts)

    def front_month(self, on_date: date) -> str | None:
        """Instrument key of the nearest future not yet expired on `on_date`.

        On expiry day the contract still trades intraday, so `expiry >= on_date`
        keeps using it until it rolls the next day.
        """
        for expiry, key in self._contracts:
            if expiry >= on_date:
                return key
        return None

    def expiries(self) -> list[date]:
        return [e for e, _ in self._contracts]
