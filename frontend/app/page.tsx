import Link from "next/link";
import { Nav } from "@/components/nav";
import { getMockRunList } from "@/lib/mock-data";
import { fmtDate, fmtPct } from "@/lib/format";

export default function HomePage() {
  const runs = getMockRunList();
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[1200px] px-6 pt-16 pb-24">
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
              {runs.length} completed
            </span>
          </div>
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
                  <th className="text-right font-normal py-3.5 px-5"></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r: any) => {
                  const pos = r.totalReturnPct >= 0;
                  return (
                    <tr
                      key={r.id}
                      className="divider-b last:border-b-0 hover:bg-[var(--color-surface-1)]/60 transition-colors"
                    >
                      <td className="py-4 px-5 font-medium">{r.strategyName}</td>
                      <td className="py-4 px-5 text-[var(--color-ink-muted)]">
                        {r.underlying}
                      </td>
                      <td className="py-4 px-5 text-[var(--color-ink-muted)]">
                        {fmtDate(r.start)} to {fmtDate(r.end)}
                      </td>
                      <td
                        className={`py-4 px-5 text-right font-medium ${
                          pos
                            ? "text-[var(--color-positive)]"
                            : "text-[var(--color-negative)]"
                        }`}
                      >
                        {fmtPct(r.totalReturnPct, 2, { sign: true })}
                      </td>
                      <td className="py-4 px-5 text-right">{r.sharpe.toFixed(2)}</td>
                      <td className="py-4 px-5 text-right text-[var(--color-ink-muted)]">
                        {r.trades}
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
        </section>
      </main>
    </div>
  );
}
