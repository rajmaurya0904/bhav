"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { MetricCard } from "@/components/metric-card";
import { EquityCurve } from "@/components/equity-curve";
import { DrawdownChart } from "@/components/drawdown-chart";
import { PnLDistribution } from "@/components/pnl-distribution";
import { TradeTable } from "@/components/trade-table";
import { getRun, RunDetail, withDrawdown } from "@/lib/api";
import { fmtDate, fmtINR, fmtPct } from "@/lib/format";

export default function BacktestDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getRun(id);
        if (!cancelled) setRun(data);
        if (data.status.status === "completed" || data.status.status === "failed") {
          return true;
        }
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      }
      return false;
    };
    load();
    const t = setInterval(async () => {
      const done = await load();
      if (done) clearInterval(t);
    }, 2500);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [id]);

  if (error) {
    return <ErrorLayout id={id} message={error} />;
  }
  if (!run) {
    return <LoadingLayout id={id} />;
  }
  const s = run.status.status;
  if (s === "queued" || s === "running") {
    return <ProgressLayout id={id} run={run} />;
  }
  if (s === "failed") {
    return <FailedLayout id={id} run={run} />;
  }
  return <CompletedLayout id={id} run={run} />;
}

function CompletedLayout({ id, run }: { id: string; run: RunDetail }) {
  const m = run.metrics;
  const equity = run.equity_curve ?? [];
  const trades = run.trades ?? [];
  const equityWithDD = withDrawdown(equity);
  const strategyName = run.manifest?.strategy ?? id;
  const cfg = (run.manifest?.config ?? {}) as {
    start?: string;
    end?: string;
    underlying?: string;
    capital?: number;
    lot_size?: number;
  };
  const trimmedEquity = equity.map((p) => ({ ...p, t: p.t.slice(0, 10) }));
  const trimmedDD = equityWithDD.map((p) => ({ ...p, t: p.t.slice(0, 10) }));

  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[1200px] px-6 pt-12 pb-24">
        <Breadcrumb id={id} />

        <div className="flex flex-wrap items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-[42px] tracking-[-0.03em] font-medium leading-[1.05]">
              {strategyName}
            </h1>
            <p className="mt-3 text-[15px] text-[var(--color-ink-muted)]">
              {shortUnderlying(cfg.underlying)}
              {cfg.start && cfg.end ? ` · ${fmtDate(cfg.start)} to ${fmtDate(cfg.end)}` : ""}
              {" · 1-minute bars"}
            </p>
          </div>
        </div>

        {m ? (
          <MetricsGrid m={m} />
        ) : (
          <EmptyMetricsGrid />
        )}

        <ChartCard title="Equity curve" subtitle="Bar by bar">
          {equity.length > 0 ? (
            <EquityCurve data={trimmedEquity} />
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          <ChartCard title="Drawdown" subtitle="From peak">
            {equity.length > 0 ? (
              <DrawdownChart data={trimmedDD} />
            ) : (
              <EmptyChart />
            )}
          </ChartCard>
          <ChartCard title="P&L distribution" subtitle="Per trade">
            {trades.length > 0 ? (
              <PnLDistribution
                trades={trades.map((t) => ({
                  date: t.entry_time.slice(0, 10),
                  entryTime: t.entry_time.slice(11, 16),
                  exitTime: t.exit_time.slice(11, 16),
                  symbol: t.symbol,
                  side: t.symbol.endsWith("CE") ? "CE" : "PE",
                  strike: 0,
                  qty: t.qty,
                  entryPrice: t.entry_price,
                  exitPrice: t.exit_price,
                  pnl: t.pnl_net,
                  reason: t.reason as any,
                }))}
              />
            ) : (
              <EmptyChart />
            )}
          </ChartCard>
        </div>

        <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 overflow-hidden">
          <div className="flex items-baseline justify-between p-6 pb-4">
            <h2 className="text-[20px] tracking-tight font-medium">Trade log</h2>
            <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] tabular">
              {trades.length} trades
            </span>
          </div>
          {trades.length > 0 ? (
            <TradeTable
              trades={trades.map((t) => ({
                date: t.entry_time.slice(0, 10),
                entryTime: t.entry_time.slice(11, 16),
                exitTime: t.exit_time.slice(11, 16),
                symbol: t.symbol,
                side: t.symbol.endsWith("CE") ? "CE" : "PE",
                strike: 0,
                qty: t.qty,
                entryPrice: t.entry_price,
                exitPrice: t.exit_price,
                pnl: t.pnl_net,
                reason: t.reason as any,
              }))}
            />
          ) : (
            <div className="px-6 py-10 text-[14px] text-[var(--color-ink-muted)]">
              No trades executed in this range.
            </div>
          )}
        </section>

        <RunMeta id={id} run={run} />
      </main>
    </div>
  );
}

function MetricsGrid({ m }: { m: NonNullable<RunDetail["metrics"]> }) {
  return (
    <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 mb-8">
      <div className="grid grid-cols-2 md:grid-cols-4">
        <MetricCard
          label="Total return"
          value={fmtPct(m.total_return_pct, 2, { sign: true })}
          sub={`${fmtINR(m.ending_equity)} from ${fmtINR(m.starting_capital)}`}
          tone={m.total_return_pct >= 0 ? "positive" : "negative"}
        />
        <MetricCard
          label="CAGR"
          value={fmtPct(m.cagr_pct, 2, { sign: true })}
          tone={m.cagr_pct >= 0 ? "positive" : "negative"}
        />
        <MetricCard
          label="Sharpe"
          value={m.sharpe.toFixed(2)}
          sub={`Sortino ${m.sortino.toFixed(2)}`}
        />
        <MetricCard
          label="Max drawdown"
          value={fmtPct(m.max_drawdown_pct, 2)}
          sub={fmtINR(m.max_drawdown_amount)}
          tone="negative"
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 divider-t">
        <MetricCard
          label="Trades"
          value={m.total_trades.toString()}
          sub={`${m.winning_trades} wins / ${m.losing_trades} losses`}
        />
        <MetricCard
          label="Win rate"
          value={fmtPct(m.win_rate_pct, 1)}
          sub={`Profit factor ${m.profit_factor.toFixed(2)}`}
        />
        <MetricCard
          label="Avg win / loss"
          value={`${fmtINR(m.avg_win)} / ${fmtINR(m.avg_loss)}`}
          sub={`Expectancy ${fmtINR(m.expectancy)}`}
        />
        <MetricCard
          label="Costs paid"
          value={fmtINR(m.total_costs)}
          sub={`${fmtPct(m.exposure_time_pct, 1)} time in market`}
        />
      </div>
    </section>
  );
}

function EmptyMetricsGrid() {
  return (
    <section className="rounded-lg border border-dashed border-[var(--color-border-warm)] bg-white/40 mb-8 px-6 py-10 text-center text-[14px] text-[var(--color-ink-muted)]">
      Metrics not yet available.
    </section>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-6 mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-[20px] tracking-tight font-medium">{title}</h2>
        <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
          {subtitle}
        </span>
      </div>
      {children}
    </section>
  );
}

function EmptyChart() {
  return (
    <div className="h-[220px] flex items-center justify-center text-[13px] text-[var(--color-ink-muted)]">
      No data available.
    </div>
  );
}

function ProgressLayout({ id, run }: { id: string; run: RunDetail }) {
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[720px] px-6 pt-24 pb-24">
        <Breadcrumb id={id} />
        <h1 className="text-[36px] tracking-[-0.03em] font-medium">
          {run.status.status === "queued" ? "Queued" : "Running"}
        </h1>
        <p className="mt-3 text-[16px] text-[var(--color-ink-muted)]">
          Bhav is fetching candles and simulating your strategy. This page
          refreshes every 2.5 seconds.
        </p>
        <div className="mt-8 rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-6">
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Progress
          </div>
          <div className="text-[16px] font-medium">
            {run.status.progress ?? "..."}
          </div>
        </div>
      </main>
    </div>
  );
}

function FailedLayout({ id, run }: { id: string; run: RunDetail }) {
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[720px] px-6 pt-24 pb-24">
        <Breadcrumb id={id} />
        <h1 className="text-[36px] tracking-[-0.03em] font-medium text-[var(--color-negative)]">
          Backtest failed
        </h1>
        <div className="mt-6 rounded-lg border border-[var(--color-negative)]/30 bg-white/40 p-6">
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Error
          </div>
          <pre className="text-[13px] font-mono text-[var(--color-ink)] whitespace-pre-wrap">
            {run.status.error ?? "unknown error"}
          </pre>
        </div>
        <div className="mt-6">
          <Link
            href="/new"
            className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-[13px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors"
          >
            Start a new backtest
          </Link>
        </div>
      </main>
    </div>
  );
}

function LoadingLayout({ id }: { id: string }) {
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[720px] px-6 pt-24 pb-24">
        <Breadcrumb id={id} />
        <div className="text-[14px] text-[var(--color-ink-muted)]">Loading...</div>
      </main>
    </div>
  );
}

function ErrorLayout({ id, message }: { id: string; message: string }) {
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[720px] px-6 pt-24 pb-24">
        <Breadcrumb id={id} />
        <h1 className="text-[28px] font-medium">Cannot reach the API</h1>
        <p className="mt-3 text-[14px] text-[var(--color-ink-muted)]">
          Start it with{" "}
          <code className="font-mono text-[12px] bg-[var(--color-code-bg)] px-1.5 py-0.5 rounded">
            bhav-server
          </code>
          .
        </p>
        <pre className="mt-6 text-[12px] font-mono text-[var(--color-ink-muted)] whitespace-pre-wrap">
          {message}
        </pre>
      </main>
    </div>
  );
}

function Breadcrumb({ id }: { id: string }) {
  return (
    <div className="mb-2 text-[13px] text-[var(--color-ink-muted)]">
      <Link href="/" className="hover:text-[var(--color-ink)] transition-colors">
        Runs
      </Link>
      <span className="mx-2">/</span>
      <span className="text-[var(--color-ink)]">{id}</span>
    </div>
  );
}

function RunMeta({ id, run }: { id: string; run: RunDetail }) {
  const cfg = (run.manifest?.config ?? {}) as {
    start?: string;
    end?: string;
    capital?: number;
    lot_size?: number;
    underlying?: string;
  };
  return (
    <section className="mt-12 pt-8 divider-t">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8 text-[14px]">
        <div>
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Run ID
          </div>
          <div className="font-mono text-[13px]">{id}</div>
        </div>
        <div>
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Created
          </div>
          <div>
            {run.manifest?.created_at
              ? new Date(run.manifest.created_at).toLocaleString("en-IN")
              : "-"}
          </div>
        </div>
        <div>
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Capital / lot size
          </div>
          <div>
            {cfg.capital ? `Rs ${cfg.capital.toLocaleString("en-IN")}` : "-"}
            {cfg.lot_size ? ` · ${cfg.lot_size}` : ""}
          </div>
        </div>
        <div>
          <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
            Data source
          </div>
          <div>Upstox v2 historical candle API</div>
        </div>
      </div>
    </section>
  );
}

function shortUnderlying(k?: string): string {
  if (!k) return "-";
  return k.split("|")[1] ?? k;
}
