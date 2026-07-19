"""Underlying spec table: Upstox instrument_key, display name, lot size, ATM step.

Lot sizes reflect the NSE/BSE revisions effective from the January 2026 expiry
cycle. Verify against the latest exchange circular before running a live-money
strategy. All values can be overridden on the CLI (`--lot-size`) or in the API
form.

Sources: NSE circular FAOP70616, BSE lot-size revision Dec 2025.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderlyingSpec:
    key: str          # Upstox instrument_key
    display: str      # human-readable name shown in UI
    lot_size: int
    atm_step: int     # strike interval
    # Futures identity in the Upstox instrument master, used to auto-roll the
    # front-month contract for futures-basis ATM. `futures_name` matches the
    # master's `name` field; `futures_segment` its `segment` (NSE_FO / BSE_FO).
    futures_name: str | None = None
    futures_segment: str | None = None


UNDERLYINGS: tuple[UnderlyingSpec, ...] = (
    UnderlyingSpec("NSE_INDEX|Nifty 50", "NIFTY 50", 65, 50, "NIFTY", "NSE_FO"),
    UnderlyingSpec("NSE_INDEX|Nifty Bank", "BANK NIFTY", 25, 100, "BANKNIFTY", "NSE_FO"),
    UnderlyingSpec("NSE_INDEX|Nifty Fin Service", "FIN NIFTY", 65, 50, "FINNIFTY", "NSE_FO"),
    UnderlyingSpec("NSE_INDEX|NIFTY MID SELECT", "MIDCAP NIFTY", 120, 25, "MIDCPNIFTY", "NSE_FO"),
    UnderlyingSpec("NSE_INDEX|Nifty Next 50", "NIFTY NEXT 50", 25, 100, "NIFTYNXT50", "NSE_FO"),
    UnderlyingSpec("BSE_INDEX|SENSEX", "SENSEX", 20, 100, "SENSEX", "BSE_FO"),
    UnderlyingSpec("BSE_INDEX|BANKEX", "BANKEX", 30, 100, "BANKEX", "BSE_FO"),
    UnderlyingSpec("BSE_INDEX|SENSEX 50", "SENSEX 50", 60, 100, "SENSEX50", "BSE_FO"),
)

_BY_KEY = {u.key: u for u in UNDERLYINGS}


def by_key(key: str) -> UnderlyingSpec | None:
    """Return the spec for a given Upstox instrument_key, or None."""
    return _BY_KEY.get(key)


def default_lot_size(key: str, fallback: int = 65) -> int:
    spec = by_key(key)
    return spec.lot_size if spec else fallback


def default_atm_step(key: str, fallback: int = 50) -> int:
    spec = by_key(key)
    return spec.atm_step if spec else fallback


def futures_identity(key: str) -> tuple[str, str] | None:
    """(futures_name, segment) for auto-rolling the front-month future, or None
    if this underlying has no known futures mapping (pass --futures-key by hand)."""
    spec = by_key(key)
    if spec and spec.futures_name and spec.futures_segment:
        return (spec.futures_name, spec.futures_segment)
    return None
