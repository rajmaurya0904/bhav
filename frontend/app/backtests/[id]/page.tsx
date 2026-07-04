import Link from "next/link";
import { Nav } from "@/components/nav";
import { MetricCard } from "@/components/metric-card";
import { EquityCurve } from "@/components/equity-curve";
import { DrawdownChart } from "@/components/drawdown-chart";
import { PnLDistribution } from "@/components/pnl-distribution";
import { TradeTable } from "@/components/trade-table";
import { getMockRun } from "@/lib/mock-data";
import { fmtDate, fmtINR, fmtPct } from "@/lib/format";

export default async function BacktestDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = getMockRun(id);
  const m = run.metrics;
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[1200px] px-6 pt-12 pb-24">
        <div className="mb-2 text-[13px] text-[var(--color-ink-muted)]">
          <Link href="/" className="hover:text-[var(--color-ink)] transition-colors">
            Runs
          </Link>
          <span className="mx-2">/</span>
          <span className="text-[var(--color-ink)]">{run.id}</span>
        </div>

        <div className="flex flex-wrap items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-[42px] tracking-[-0.03em] font-medium leading-[1.05]">
              {run.strategyName}
            </h1>
            <p className="mt-3 text-[15px] text-[var(--color-ink-muted)]">
              {run.underlying} {" · "} {fmtDate(run.start)} to {fmtDate(run.end)}{" · "}
              1-minute bars
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="rounded-md border border-[var(--color-border-warm)] px-4 py-2 text-[13px] font-medium hover:bg-[var(--color-surface-1)] transition-colors">
              Download results
            </button>
            <button className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-[13px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors">
              Re-run
            </button>
          </div>
        </div>

        <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 mb-8">
          <div className="grid grid-cols-2 md:grid-cols-4">
            <MetricCard
              label="Total return"
              value={fmtPct(m.totalReturnPct, 2, { sign: true })}
              sub={`${fmtINR(m.endingEquity)} from ${fmtINR(m.startingCapital)}`}
              tone={m.totalReturnPct >= 0 ? "positive" : "negative"}
            />
            <MetricCard
              label="CAGR"
              value={fmtPct(m.cagrPct, 2, { sign: true })}
              tone={m.cagrPct >= 0 ? "positive" : "negative"}
            />
            <MetricCard
              label="Sharpe"
              value={m.sharpe.toFixed(2)}
              sub={`Sortino ${m.sortino.toFixed(2)}`}
            />
            <MetricCard
              label="Max drawdown"
              value={fmtPct(m.maxDrawdownPct, 2)}
              sub={fmtINR(m.maxDrawdownAmount)}
              tone="negative"
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 divider-t">
            <MetricCard
              label="Trades"
              value={m.totalTrades.toString()}
              sub={`${m.winningTrades} wins / ${m.losingTrades} losses`}
            />
            <MetricCard
              label="Win rate"
              value={fmtPct(m.winRatePct, 1)}
              sub={`Profit factor ${m.profitFactor.toFixed(2)}`}
            />
            <MetricCard
              label="Avg win / loss"
              value={`${fmtINR(m.avgWin)} / ${fmtINR(m.avgLoss)}`}
              sub={`Expectancy ${fmtINR(m.expectancy)}`}
            />
            <MetricCard
              label="Costs paid"
              value={fmtINR(m.totalCosts)}
              sub={`${fmtPct(m.exposureTimePct, 1)} time in market`}
            />
          </div>
        </section>

        <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-6 mb-8">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-[20px] tracking-tight font-medium">Equity curve</h2>
            <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
              Daily close
            </span>
          </div>
          <EquityCurve data={run.equity} />
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-6">
            <div className="flex items-baseline justify-between mb-4">
              <h2 className="text-[20px] tracking-tight font-medium">Drawdown</h2>
              <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
                From peak
              </span>
            </div>
            <DrawdownChart data={run.equity} />
          </section>
          <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-6">
            <div className="flex items-baseline justify-between mb-4">
              <h2 className="text-[20px] tracking-tight font-medium">
                P&amp;L distribution
              </h2>
              <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
                Per trade
              </span>
            </div>
            <PnLDistribution trades={run.trades} />
          </section>
        </div>

        <section className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 overflow-hidden">
          <div className="flex items-baseline justify-between p-6 pb-4">
            <h2 className="text-[20px] tracking-tight font-medium">Trade log</h2>
            <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] tabular">
              {run.trades.length} trades
            </span>
          </div>
          <TradeTable trades={run.trades} />
        </section>

        <section className="mt-12 pt-8 divider-t">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-[14px]">
            <div>
              <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
                Run ID
              </div>
              <div className="font-mono text-[13px]">{run.id}</div>
            </div>
            <div>
              <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
                Created
              </div>
              <div>{new Date(run.createdAt).toLocaleString("en-IN")}</div>
            </div>
            <div>
              <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)] mb-2">
                Data source
              </div>
              <div>Upstox v2 historical candle API</div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
