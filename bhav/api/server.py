"""FastAPI results server.

Endpoints:
    GET  /api/runs           list all completed + running runs
    GET  /api/runs/{id}      full detail: metrics, equity curve, trades
    POST /api/runs           launch a new backtest (multipart: strategy .py + config)
    GET  /api/health         liveness

Runs execute in a background thread. State is polled from `runs/<id>/status.json`.
"""
from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from bhav.cli import _load_strategy
from bhav.data.cache import ParquetCache
from bhav.data.instruments import InstrumentResolver
from bhav.data.reader import DataReader
from bhav.data.upstox_client import UpstoxClient
from bhav.engine.bar_engine import BarEngine, EngineConfig
from bhav.metrics.report import compute_metrics
from bhav.output.writer import ResultWriter

RUNS_DIR = Path("runs")
STRATEGIES_DIR = Path("strategies")

app = FastAPI(title="Bhav Runs API", version="0.1.0-alpha")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


def _write_status(run_id: str, **fields) -> None:
    d = _run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "status.json"
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            existing = {}
    existing.update(fields)
    existing["updated_at"] = datetime.utcnow().isoformat() + "Z"
    path.write_text(json.dumps(existing, indent=2, default=str))


def _run_backtest_thread(
    run_id: str,
    strategy_path: Path,
    token: str,
    underlying: str,
    start: date,
    end: date,
    capital: float,
    lot_size: int,
) -> None:
    try:
        _write_status(run_id, status="running", progress="loading_strategy")
        strategy = _load_strategy(strategy_path)
        _write_status(run_id, status="running", progress="fetching_data", strategy_name=strategy.name)

        with UpstoxClient(token) as client:
            cache = ParquetCache()
            reader = DataReader(client, cache)
            resolver = InstrumentResolver(client, underlying)
            cfg = EngineConfig(
                underlying_key=underlying,
                start=start,
                end=end,
                starting_capital=capital,
                lot_size=lot_size,
            )
            engine = BarEngine(cfg, reader, resolver)
            _write_status(run_id, progress="simulating")
            portfolio = engine.run(strategy)

        metrics = compute_metrics(portfolio)
        writer = ResultWriter(RUNS_DIR)
        writer.write(
            run_id, portfolio, metrics,
            strategy_name=strategy.name,
            config={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "capital": capital,
                "lot_size": lot_size,
                "underlying": underlying,
            },
        )
        _write_status(run_id, status="completed", progress="done")
    except Exception as e:
        _write_status(
            run_id,
            status="failed",
            error=str(e),
            traceback=traceback.format_exc(limit=6),
        )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0-alpha"}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    out: list[dict] = []
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        status_path = d / "status.json"
        if not (manifest_path.exists() or status_path.exists()):
            continue
        entry: dict[str, Any] = {"id": d.name}
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text())
            entry["strategy_name"] = m.get("strategy")
            entry["created_at"] = m.get("created_at")
            entry["config"] = m.get("config", {})
        if status_path.exists():
            s = json.loads(status_path.read_text())
            entry["status"] = s.get("status", "unknown")
            entry["error"] = s.get("error")
        else:
            entry["status"] = "completed"
        metrics_path = d / "metrics.json"
        if metrics_path.exists():
            met = json.loads(metrics_path.read_text())
            entry["total_return_pct"] = met.get("total_return_pct")
            entry["sharpe"] = met.get("sharpe")
            entry["total_trades"] = met.get("total_trades")
            entry["win_rate_pct"] = met.get("win_rate_pct")
        out.append(entry)
    return out


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    d = _run_dir(run_id)
    if not d.exists():
        raise HTTPException(404, f"run {run_id} not found")
    result: dict[str, Any] = {"id": run_id}
    if (d / "manifest.json").exists():
        result["manifest"] = json.loads((d / "manifest.json").read_text())
    if (d / "status.json").exists():
        result["status"] = json.loads((d / "status.json").read_text())
    else:
        result["status"] = {"status": "completed"}
    if (d / "metrics.json").exists():
        result["metrics"] = json.loads((d / "metrics.json").read_text())
    if (d / "equity_curve.parquet").exists():
        eq = pl.read_parquet(d / "equity_curve.parquet")
        result["equity_curve"] = [
            {"t": ts.isoformat(), "equity": float(eq_val)}
            for ts, eq_val in zip(eq["timestamp"], eq["equity"], strict=False)
        ]
    if (d / "trades.parquet").exists():
        tr = pl.read_parquet(d / "trades.parquet")
        result["trades"] = [
            {
                "symbol": r["symbol"],
                "entry_time": r["entry_time"].isoformat() if r["entry_time"] else None,
                "exit_time": r["exit_time"].isoformat() if r["exit_time"] else None,
                "qty": int(r["qty"]),
                "entry_price": float(r["entry_price"]),
                "exit_price": float(r["exit_price"]),
                "pnl_gross": float(r["pnl_gross"]),
                "costs": float(r["costs"]),
                "pnl_net": float(r["pnl_net"]),
                "reason": r["reason"],
            }
            for r in tr.iter_rows(named=True)
        ]
    return result


@app.post("/api/runs")
async def create_run(
    background: BackgroundTasks,
    strategy: UploadFile,
    upstox_token: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    underlying: str = Form("NSE_INDEX|Nifty 50"),
    capital: float = Form(500_000),
    lot_size: int = Form(75),
) -> dict:
    if not strategy.filename or not strategy.filename.endswith(".py"):
        raise HTTPException(400, "strategy must be a .py file")
    content = (await strategy.read()).decode("utf-8")
    if "strategy" not in content:
        raise HTTPException(
            400,
            "strategy file must expose a module-level `strategy` variable",
        )

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    strategy_path = STRATEGIES_DIR / f"{run_id}.py"
    strategy_path.write_text(content, encoding="utf-8")

    _write_status(run_id, status="queued", progress="submitted")

    try:
        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
    except ValueError as e:
        raise HTTPException(400, f"bad date format: {e}") from e

    thread = threading.Thread(
        target=_run_backtest_thread,
        args=(run_id, strategy_path, upstox_token, underlying, start_d, end_d, capital, lot_size),
        daemon=True,
    )
    thread.start()
    return {"id": run_id, "status": "queued"}


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Entry point for the `bhav-server` script."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    serve()
