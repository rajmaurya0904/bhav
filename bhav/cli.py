"""Typer CLI entry point."""
from __future__ import annotations

import importlib.util
import uuid
from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bhav.ai import (
    ClaudeNotFoundError,
    GenerationError,
    claude_available,
    generate_strategy,
)
from bhav.data.cache import ParquetCache
from bhav.data.excel_source import (
    DEFAULT_EXCEL_PATH,
    ExcelDataReader,
    ExcelDataSource,
    ExcelInstrumentResolver,
)
from bhav.data.futures import FuturesRoll, InstrumentMaster
from bhav.data.instruments import InstrumentResolver
from bhav.data.reader import DataReader
from bhav.data.underlyings import default_lot_size, futures_identity
from bhav.data.upstox_client import UpstoxClient
from bhav.engine.bar_engine import BarEngine, EngineConfig
from bhav.metrics.montecarlo import run_monte_carlo
from bhav.metrics.report import compute_metrics
from bhav.output.writer import ResultWriter

app = typer.Typer(help="Bhav: NSE options backtester", no_args_is_help=True)
console = Console()


@app.callback()
def _main() -> None:
    """Bhav: NSE options backtesting engine."""


def _load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location("user_strategy", path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"Could not load strategy from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "strategy"):
        raise typer.BadParameter(f"{path} must expose a `strategy` variable")
    return mod.strategy


@app.command()
def run(
    strategy_path: Path = typer.Argument(..., help="Path to a Python file with `strategy = MyStrategy()`"),
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    token: str | None = typer.Option(None, envvar="UPSTOX_TOKEN", help="Required unless --data-source excel."),
    data_source: str = typer.Option(
        "upstox", help="'upstox' (live API, needs --token) or 'excel' (bundled offline NIFTY dataset, no token needed)."
    ),
    excel_path: Path = typer.Option(
        DEFAULT_EXCEL_PATH, help="Only used with --data-source excel. Path to a workbook with Spot_1min/ATM_Options_1min sheets."
    ),
    underlying: str = typer.Option("NSE_INDEX|Nifty 50"),
    capital: float = typer.Option(500_000),
    lot_size: int = typer.Option(0, help="Override lot size. 0 = auto-lookup from underlying."),
    warmup_days: int = typer.Option(0, help="Trading days before --start to feed the strategy (no trades placed)."),
    atm_reference: str = typer.Option(
        "spot", help="What price picks the ATM strike: 'spot' (default) or 'futures'. NIFTY options price off the future; 'futures' removes the spot-vs-future basis bias."
    ),
    futures_key: str | None = typer.Option(
        None, help="Pin a specific future for --atm-reference futures. Omit to auto-roll the front-month contract per day (upstox mode only)."
    ),
    out_dir: Path = typer.Option(Path("runs")),
) -> None:
    """Run a backtest and write results to `runs/<run_id>/`."""
    if data_source not in ("upstox", "excel"):
        raise typer.BadParameter("--data-source must be 'upstox' or 'excel'")
    if data_source == "upstox" and not token:
        raise typer.BadParameter("--token (or UPSTOX_TOKEN) is required for --data-source upstox")
    if data_source == "excel" and underlying != "NSE_INDEX|Nifty 50":
        raise typer.BadParameter(
            "the bundled excel dataset is NIFTY 50 only; drop --underlying or use --data-source upstox"
        )
    if atm_reference not in ("spot", "futures"):
        raise typer.BadParameter("--atm-reference must be 'spot' or 'futures'")
    if atm_reference == "futures":
        if data_source == "excel":
            raise typer.BadParameter(
                "--atm-reference futures needs live futures candles; not available in excel mode"
            )
        if not futures_key and futures_identity(underlying) is None:
            raise typer.BadParameter(
                f"--atm-reference futures can't auto-roll {underlying} (no futures mapping); "
                "pass --futures-key explicitly"
            )
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise typer.BadParameter(f"--start {start} is after --end {end}")

    strat = _load_strategy(strategy_path)
    resolved_lot = lot_size or default_lot_size(underlying)

    def _run_with(reader, resolver, futures_roll=None):
        cfg = EngineConfig(
            underlying_key=underlying,
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
            starting_capital=capital,
            lot_size=resolved_lot,
            warmup_days=warmup_days,
            atm_reference=atm_reference,
            futures_key=futures_key,
            futures_auto=futures_roll is not None,
        )
        engine = BarEngine(cfg, reader, resolver, futures_roll=futures_roll)
        console.print(
            f"[bold]Running[/bold] {strat.name} from {start} to {end} "
            f"(underlying={underlying}, lot={resolved_lot}, source={data_source})..."
        )
        return engine.run(strat)

    if data_source == "excel":
        source = ExcelDataSource(excel_path)
        portfolio = _run_with(ExcelDataReader(source), ExcelInstrumentResolver(source))
    else:
        # Build the front-month roller when futures ATM is requested without a pinned key.
        futures_roll = None
        if atm_reference == "futures" and not futures_key:
            name, segment = futures_identity(underlying)  # validated above
            futures_roll = FuturesRoll.from_master(InstrumentMaster(), name, segment)
            console.print(
                f"[dim]Auto-rolling front-month {name} futures for ATM "
                f"({len(futures_roll.expiries())} contracts in master).[/dim]"
            )
        with UpstoxClient(token) as client:
            cache = ParquetCache()
            portfolio = _run_with(
                DataReader(client, cache),
                InstrumentResolver(client, underlying),
                futures_roll=futures_roll,
            )

    metrics = compute_metrics(portfolio)
    montecarlo = run_monte_carlo(portfolio)
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    writer = ResultWriter(out_dir)
    path = writer.write(
        run_id, portfolio, metrics,
        montecarlo=montecarlo,
        strategy_name=strat.name,
        config={
            "start": start,
            "end": end,
            "capital": capital,
            "lot_size": resolved_lot,
            "data_source": data_source,
            "underlying": underlying,
            "warmup_days": warmup_days,
        },
    )
    _print_summary(metrics)
    if montecarlo is not None:
        _print_montecarlo(montecarlo)
    console.print(f"\n[dim]Results written to[/dim] [bold]{path}[/bold]")


def _print_summary(m):
    t = Table(title="Summary", show_header=False, border_style="dim")
    t.add_column("k", style="dim")
    t.add_column("v")
    t.add_row("Total return", f"{m.total_return_pct:+.2f}%")
    t.add_row("CAGR", f"{m.cagr_pct:+.2f}%")
    t.add_row("Sharpe", f"{m.sharpe:.2f}")
    t.add_row("Sortino", "inf (no losing bars)" if m.sortino is None else f"{m.sortino:.2f}")
    t.add_row("Max drawdown", f"{m.max_drawdown_pct:.2f}%")
    t.add_row("Trades", f"{m.total_trades} ({m.win_rate_pct:.1f}% win rate)")
    t.add_row("Profit factor", "inf (no losses)" if m.profit_factor is None else f"{m.profit_factor:.2f}")
    t.add_row("Total costs", f"Rs {m.total_costs:,.0f}")
    console.print(t)


def _print_montecarlo(mc) -> None:
    t = Table(title="Monte Carlo (1000 bootstraps)", show_header=False, border_style="dim")
    t.add_column("k", style="dim")
    t.add_column("v")
    t.add_row("Return 5-95%", f"{mc.p5_total_return_pct:+.1f}%  ..  {mc.p95_total_return_pct:+.1f}%")
    t.add_row("Median max DD", f"{mc.median_max_drawdown_pct:.1f}%")
    t.add_row("Worst-case DD (p95)", f"{mc.p95_max_drawdown_pct:.1f}%")
    t.add_row("Prob. of profit", f"{mc.prob_profit:.1f}%")
    t.add_row("Risk of ruin", f"{mc.risk_of_ruin_pct:.1f}%")
    console.print(t)


@app.command()
def generate(
    description: str = typer.Argument(
        ..., help="Plain-English description of the strategy to generate."
    ),
    out: Path = typer.Option(..., "--out", "-o", help="Where to write the .py file."),
    model: str | None = typer.Option(None, help="Override the Claude model (e.g. claude-opus-4-8)."),
    force: bool = typer.Option(False, "--force", help="Overwrite the output file if it exists."),
) -> None:
    """Generate a strategy file from a description using the local `claude` CLI.

    No API key needed - this drives the Claude Code CLI you already signed into.
    """
    if not claude_available():
        console.print(
            "[bold red]claude CLI not found.[/bold red] Install Claude Code "
            "(https://claude.com/claude-code) and run `claude` once to sign in."
        )
        raise typer.Exit(1)
    if out.exists() and not force:
        raise typer.BadParameter(f"{out} already exists; pass --force to overwrite")

    console.print("[dim]Generating[/dim] via claude CLI (this can take a moment)...")
    try:
        result = generate_strategy(description, model=model)
    except ClaudeNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1) from e
    except GenerationError as e:
        console.print(f"[bold red]Generation failed:[/bold red] {e}")
        raise typer.Exit(1) from e

    if not result.ok:
        console.print("[bold yellow]Warning: generated code failed validation:[/bold yellow]")
        for v in result.violations:
            console.print(f"  - {v}")
        console.print("[dim]Review it carefully before running.[/dim]")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.code, encoding="utf-8")
    label = result.name or "unnamed"
    console.print(f"[green]Wrote[/green] [bold]{out}[/bold] (strategy: {label})")
    console.print(f"[dim]Run it:[/dim] bhav run {out} --start 2025-08-01 --end 2025-08-15 --data-source excel")


if __name__ == "__main__":
    app()
