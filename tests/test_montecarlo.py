"""Monte Carlo bootstrap: determinism, tail stats, and the too-few-trades guard."""
from types import SimpleNamespace

from bhav.metrics.montecarlo import _percentile, run_monte_carlo


def _portfolio(pnls, starting_capital=100_000.0):
    return SimpleNamespace(
        starting_capital=starting_capital,
        closed_trades=[SimpleNamespace(pnl_net=p) for p in pnls],
    )


def test_percentile_endpoints_and_interpolation():
    vals = [0.0, 10.0, 20.0, 30.0, 40.0]
    assert _percentile(vals, 0) == 0.0
    assert _percentile(vals, 100) == 40.0
    assert _percentile(vals, 50) == 20.0


def test_returns_none_for_too_few_trades():
    assert run_monte_carlo(_portfolio([100, 200, -50])) is None


def test_deterministic_with_fixed_seed():
    pnls = [100, -50, 200, -30, 80, -120, 60, 40, -20, 150]
    a = run_monte_carlo(_portfolio(pnls), n_sims=500, seed=7)
    b = run_monte_carlo(_portfolio(pnls), n_sims=500, seed=7)
    assert a.to_dict() == b.to_dict()


def test_all_winning_trades_never_ruin():
    pnls = [100] * 20
    mc = run_monte_carlo(_portfolio(pnls), n_sims=300)
    assert mc.risk_of_ruin_pct == 0.0
    assert mc.prob_profit == 100.0
    assert mc.p5_total_return_pct > 0


def test_catastrophic_losses_show_ruin():
    # each trade wipes ~40% of a 100k account; ruin (50% floor) is near-certain
    pnls = [-40_000, -35_000, 5_000, -30_000, 2_000, -45_000, 1_000, -20_000]
    mc = run_monte_carlo(_portfolio(pnls), n_sims=500)
    assert mc.risk_of_ruin_pct > 0
    assert mc.p95_max_drawdown_pct > mc.median_max_drawdown_pct
