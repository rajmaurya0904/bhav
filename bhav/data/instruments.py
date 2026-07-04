"""Instrument resolver: (date, spot, option_type) -> Upstox instrument_key."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from bhav.data.underlyings import default_atm_step
from bhav.data.upstox_client import OptionContract, UpstoxClient


@dataclass(frozen=True)
class ResolvedOption:
    contract: OptionContract
    adjusted: bool  # True if fallback strike was used


class InstrumentResolver:
    """Handles expiry selection, ATM rounding, strike-not-found fallback."""

    def __init__(
        self,
        client: UpstoxClient,
        underlying_key: str,
        *,
        atm_step: int | None = None,
        fallback_offsets: tuple[int, ...] = (1, -1, 2, -2),
    ) -> None:
        self.client = client
        self.underlying_key = underlying_key
        self.atm_step = atm_step if atm_step is not None else default_atm_step(underlying_key)
        self.fallback_offsets = fallback_offsets
        self._expiries: list[date] | None = None
        self._chain_cache: dict[date, dict[tuple[int, str], OptionContract]] = {}

    def expiries(self) -> list[date]:
        if self._expiries is None:
            self._expiries = self.client.get_expired_expiries(self.underlying_key)
        return self._expiries

    def nearest_expiry(self, on_date: date, kind: str = "weekly") -> date | None:
        candidates = [e for e in self.expiries() if e >= on_date]
        if not candidates:
            return None
        return min(candidates)

    def atm_strike(self, spot: float) -> int:
        return int(round(spot / self.atm_step) * self.atm_step)

    def _chain(self, expiry: date) -> dict[tuple[int, str], OptionContract]:
        if expiry not in self._chain_cache:
            contracts = self.client.get_expired_contracts(self.underlying_key, expiry)
            self._chain_cache[expiry] = {(c.strike, c.option_type): c for c in contracts}
        return self._chain_cache[expiry]

    def resolve(
        self, expiry: date, strike: int, option_type: str
    ) -> ResolvedOption | None:
        chain = self._chain(expiry)
        key = (strike, option_type)
        if key in chain:
            return ResolvedOption(contract=chain[key], adjusted=False)
        for offset in self.fallback_offsets:
            k = (strike + offset * self.atm_step, option_type)
            if k in chain:
                return ResolvedOption(contract=chain[k], adjusted=True)
        return None
