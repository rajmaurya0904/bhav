"""Realistic NSE options cost model. Wrong here = wrong backtest."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostBreakdown:
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_txn: float = 0.0
    sebi: float = 0.0
    stamp: float = 0.0
    gst: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.brokerage + self.stt + self.exchange_txn
            + self.sebi + self.stamp + self.gst
        )


@dataclass
class CostModel:
    """Base cost model. Override for other jurisdictions."""

    slippage_ticks: float = 1.0
    tick_size: float = 0.05

    def slippage(self, price: float, qty: int, is_buy: bool) -> float:
        return self.slippage_ticks * self.tick_size * qty * (1 if is_buy else -1)

    def costs(
        self, price: float, qty: int, is_buy: bool, exercised_itm: bool = False
    ) -> CostBreakdown:
        raise NotImplementedError


@dataclass
class IndianCostModel(CostModel):
    """NSE options cost stack. Numbers current as of 2025.

    - STT: 0.0625% of premium on sell side; 0.125% of settlement value if
      exercised in-the-money at expiry.
    - Brokerage: flat 20/order default (Zerodha/Upstox style).
    - Exchange txn: 0.03503% of premium.
    - SEBI: 10/crore = 0.0001% of premium.
    - Stamp duty: 0.003% of premium on buy side.
    - GST: 18% on (brokerage + exchange + SEBI).
    """

    brokerage_per_order: float = 20.0
    exchange_txn_rate: float = 0.00003503
    sebi_rate: float = 0.000001
    stamp_rate_buy: float = 0.00003
    stt_sell_rate: float = 0.000625
    stt_exercised_rate: float = 0.00125
    gst_rate: float = 0.18

    def costs(
        self, price: float, qty: int, is_buy: bool, exercised_itm: bool = False
    ) -> CostBreakdown:
        turnover = price * qty
        b = CostBreakdown()
        b.brokerage = min(self.brokerage_per_order, 0.0003 * turnover) if turnover else 0.0
        b.exchange_txn = self.exchange_txn_rate * turnover
        b.sebi = self.sebi_rate * turnover
        if is_buy:
            b.stamp = self.stamp_rate_buy * turnover
        else:
            if exercised_itm:
                b.stt = self.stt_exercised_rate * turnover
            else:
                b.stt = self.stt_sell_rate * turnover
        b.gst = self.gst_rate * (b.brokerage + b.exchange_txn + b.sebi)
        return b
