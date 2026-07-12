"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { listRuns, RunSummary, API_BASE } from "@/lib/api";
import { fmtDate, fmtPct } from "@/lib/format";

export default function HomePage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await listRuns();
        if (!cancelled) setRuns(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      }
    };
    load();
    const t = setInterval(load, 4000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <Nav />
      <main className="flex-1 mx-auto max-w-[1200px] px-6 pt-16 pb-24 w-full">
        <section className="max-w-[720px] mb-16">
          <h1 className="text-[52px] leading-[1.05] tracking-[-0.03em] font-medium">
            A backtester built for how Indian options
            <br />
            traders actually think.
          </h1>
          <p className="mt-6 text-[17px] leading-[1.6] text-[var(--color-ink-muted)] max-w-[560px]">
            Bar-by-bar simulation on 1-minute NIFTY spot and option chain data
            from Upstox. Realistic Indian cost stack. Deterministic Parquet
            outputs you can trust.
          </p>
          <div className="mt-8 flex items-center gap-4">
            <Link
              href="/new"
              className="rounded-md bg-[var(--color-primary)] px-4 py-2.5 text-[14px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors"
            >
              Run a backtest
            </Link>
            <a
              href="#recent"
              className="rounded-md border border-[var(--color-border-warm)] px-4 py-2.5 text-[14px] font-medium text-[var(--color-ink)] hover:bg-[var(--color-surface-1)] transition-colors"
            >
              See recent runs
            </a>
          </div>
        </section>

        <section id="recent" className="mt-24">
          <div className="flex items-baseline justify-between mb-6">
            <h2 className="text-[24px] tracking-tight font-medium">Recent runs</h2>
            <span className="text-[13px] text-[var(--color-ink-muted)] tabular">
              {runs === null
                ? "Loading..."
                : error
                ? "API offline"
                : `${runs.length} total`}
            </span>
          </div>
          {error && (
            <div className="mb-4 rounded-md border border-[var(--color-border-warm)] bg-[var(--color-surface-1)]/60 px-4 py-3 text-[13px] text-[var(--color-ink-muted)]">
              Cannot reach {API_BASE}. Start the API with{" "}
              <code className="font-mono text-[12px] bg-[var(--color-code-bg)] px-1.5 py-0.5 rounded">
                bhav-server
              </code>
              .
            </div>
          )}
          <RunsTable runs={runs ?? []} />
        </section>
      </main>
      <Footer />
    </div>
  );
}

function RunsTable({ runs }: { runs: RunSummary[] }) {
  if (runs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--color-border-warm)] bg-white/40 px-6 py-16 text-center">
        <p className="text-[15px] font-medium">No runs yet.</p>
        <p className="mt-2 text-[13px] text-[var(--color-ink-muted)]">
          Head to{" "}
          <Link href="/new" className="text-[var(--color-primary)] hover:underline">
            new backtest
          </Link>{" "}
          to launch your first one.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-[var(--color-border-warm)] bg-white/40 overflow-hidden">
      <table className="w-full text-[14px] tabular">
        <thead>
          <tr className="divider-b text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            <th className="text-left font-normal py-3.5 px-5">Strategy</th>
            <th className="text-left font-normal py-3.5 px-5">Underlying</th>
            <th className="text-left font-normal py-3.5 px-5">Period</th>
            <th className="text-right font-normal py-3.5 px-5">Return</th>
            <th className="text-right font-normal py-3.5 px-5">Sharpe</th>
            <th className="text-right font-normal py-3.5 px-5">Trades</th>
            <th className="text-left font-normal py-3.5 px-5">Status</th>
            <th className="text-right font-normal py-3.5 px-5"></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const ret = r.total_return_pct;
            const pos = ret !== undefined && ret >= 0;
            return (
              <tr
                key={r.id}
                className="divider-b last:border-b-0 hover:bg-[var(--color-surface-1)]/60 transition-colors"
              >
                <td className="py-4 px-5 font-medium">
                  {r.strategy_name ?? r.id}
                </td>
                <td className="py-4 px-5 text-[var(--color-ink-muted)]">
                  {shortUnderlying(r.config?.underlying)}
                </td>
                <td className="py-4 px-5 text-[var(--color-ink-muted)]">
                  {r.config?.start && r.config?.end
                    ? `${fmtDate(r.config.start)} to ${fmtDate(r.config.end)}`
                    : "-"}
                </td>
                <td
                  className={`py-4 px-5 text-right font-medium ${
                    ret === undefined
                      ? "text-[var(--color-ink-muted)]"
                      : pos
                      ? "text-[var(--color-positive)]"
                      : "text-[var(--color-negative)]"
                  }`}
                >
                  {ret === undefined ? "-" : fmtPct(ret, 2, { sign: true })}
                </td>
                <td className="py-4 px-5 text-right">
                  {r.sharpe?.toFixed(2) ?? "-"}
                </td>
                <td className="py-4 px-5 text-right text-[var(--color-ink-muted)]">
                  {r.total_trades ?? "-"}
                </td>
                <td className="py-4 px-5">
                  <StatusPill status={r.status} />
                </td>
                <td className="py-4 px-5 text-right">
                  <Link
                    href={`/backtests/${r.id}`}
                    className="text-[var(--color-primary)] hover:underline"
                  >
                    Open
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    completed: ["Completed", "text-[var(--color-positive)]"],
    running: ["Running", "text-[var(--color-primary)]"],
    queued: ["Queued", "text-[var(--color-ink-muted)]"],
    failed: ["Failed", "text-[var(--color-negative)]"],
    unknown: ["Unknown", "text-[var(--color-ink-muted)]"],
  };
  const [label, cls] = map[status] ?? map.unknown;
  return <span className={`text-[13px] ${cls}`}>{label}</span>;
}

function shortUnderlying(k?: string): string {
  if (!k) return "-";
  return k.split("|")[1] ?? k;
}
