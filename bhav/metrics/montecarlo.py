"""Monte Carlo robustness via trade-sequence bootstrap.

A single backtest is one draw from a distribution: it happens to have taken the
trades in the order the market delivered them. Reshuffling and resampling those
same trades (bootstrap) shows how much of the headline return was skill versus the
luck of ordering — and, crucially, how deep the drawdown could plausibly have been.

We resample the realised per-trade net P&L with replacement, replay each resampled
sequence into an equity path, and report the distribution of ending equity, max
drawdown, and the probability the account would have been ruined.

Pure stdlib (no numpy) to match the rest of the codebase.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

from bhav.engine.portfolio import Portfolio


@dataclass
class MonteCarloReport:
    n_sims: int
    n_trades: int
    starting_capital: float
    ruin_threshold: float
    # ending equity distribution
    mean_ending_equity: float
    median_ending_equity: float
    p5_ending_equity: float
    p95_ending_equity: float
    # total return distribution
    p5_total_return_pct: float
    p95_total_return_pct: float
    # drawdown distribution (worst case is the tail that matters)
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float
    # tail risk
    prob_profit: float
    risk_of_ruin_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolated percentile of an already-sorted list (pct in 0..100)."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (pct / 100) * (len(sorted_vals) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def run_monte_carlo(
    portfolio: Portfolio,
    *,
    n_sims: int = 1000,
    seed: int = 42,
    ruin_fraction: float = 0.5,
) -> MonteCarloReport | None:
    """Bootstrap the closed trades. Returns None if there are too few trades
    (< 5) to say anything meaningful.

    `ruin_fraction`: account is "ruined" if equity ever falls to this fraction of
    starting capital (default 0.5 = a 50% peak-to-trough wipeout from the start).
    `seed`: fixed so results are reproducible run-to-run, matching Bhav's
    deterministic-output philosophy.
    """
    pnls = [t.pnl_net for t in portfolio.closed_trades]
    if len(pnls) < 5:
        return None

    start = portfolio.starting_capital
    ruin_threshold = start * ruin_fraction
    rng = random.Random(seed)
    n = len(pnls)

    ending_equities: list[float] = []
    max_drawdowns: list[float] = []
    ruined = 0

    for _ in range(n_sims):
        equity = start
        peak = start
        worst_dd_pct = 0.0
        hit_ruin = False
        for _ in range(n):
            equity += pnls[rng.randrange(n)]
            peak = max(peak, equity)
            if peak > 0:
                dd_pct = (peak - equity) / peak * 100
                worst_dd_pct = max(worst_dd_pct, dd_pct)
            if equity <= ruin_threshold:
                hit_ruin = True
        ending_equities.append(equity)
        max_drawdowns.append(worst_dd_pct)
        if hit_ruin:
            ruined += 1

    ending_equities.sort()
    max_drawdowns.sort()
    mean_end = sum(ending_equities) / n_sims
    n_profitable = sum(1 for e in ending_equities if e > start)

    return MonteCarloReport(
        n_sims=n_sims,
        n_trades=n,
        starting_capital=start,
        ruin_threshold=ruin_threshold,
        mean_ending_equity=mean_end,
        median_ending_equity=_percentile(ending_equities, 50),
        p5_ending_equity=_percentile(ending_equities, 5),
        p95_ending_equity=_percentile(ending_equities, 95),
        p5_total_return_pct=(_percentile(ending_equities, 5) - start) / start * 100,
        p95_total_return_pct=(_percentile(ending_equities, 95) - start) / start * 100,
        median_max_drawdown_pct=_percentile(max_drawdowns, 50),
        p95_max_drawdown_pct=_percentile(max_drawdowns, 95),
        prob_profit=n_profitable / n_sims * 100,
        risk_of_ruin_pct=ruined / n_sims * 100,
    )
