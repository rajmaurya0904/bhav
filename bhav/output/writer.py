"""Deterministic result writer. Parquet trades, Parquet equity, JSON metrics + manifest."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from bhav.engine.portfolio import Portfolio
from bhav.metrics.report import MetricsReport


class ResultWriter:
    def __init__(self, out_dir: Path | str) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        run_id: str,
        portfolio: Portfolio,
        metrics: MetricsReport,
        *,
        strategy_name: str,
        config: dict,
    ) -> Path:
        run_dir = self.out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        trades_df = pl.DataFrame([
            {
                "symbol": t.symbol,
                "instrument_key": t.instrument_key,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "qty": t.qty,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_gross": t.pnl_gross,
                "costs": t.costs,
                "pnl_net": t.pnl_net,
                "reason": t.reason,
            }
            for t in portfolio.closed_trades
        ]) if portfolio.closed_trades else pl.DataFrame()
        trades_path = run_dir / "trades.parquet"
        if not trades_df.is_empty():
            trades_df.write_parquet(trades_path)

        equity_df = pl.DataFrame(
            {
                "timestamp": [ts for ts, _ in portfolio.equity_curve],
                "equity": [eq for _, eq in portfolio.equity_curve],
            }
        )
        equity_path = run_dir / "equity_curve.parquet"
        equity_df.write_parquet(equity_path)

        metrics_path = run_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics.to_dict(), indent=2, default=str))

        manifest = {
            "run_id": run_id,
            "strategy": strategy_name,
            "config": config,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "artifacts": {
                "trades": str(trades_path.name),
                "equity_curve": str(equity_path.name),
                "metrics": str(metrics_path.name),
            },
            "checksums": {
                "metrics_sha256": hashlib.sha256(
                    metrics_path.read_bytes()
                ).hexdigest(),
            },
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return run_dir
