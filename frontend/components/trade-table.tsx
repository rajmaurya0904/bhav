import type { Trade } from "@/lib/mock-data";
import { fmtINR, fmtDate } from "@/lib/format";

const reasonLabel: Record<Trade["reason"], string> = {
  tgt_hit: "Target",
  sl_hit: "Stop loss",
  trail_sl: "Trail stop",
  eod_square_off: "EOD",
};

export function TradeTable({ trades }: { trades: Trade[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[14px] tabular">
        <thead>
          <tr className="divider-b text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
            <th className="text-left font-normal py-3 px-4">Date</th>
            <th className="text-left font-normal py-3 px-4">Symbol</th>
            <th className="text-left font-normal py-3 px-4">Side</th>
            <th className="text-right font-normal py-3 px-4">Entry</th>
            <th className="text-right font-normal py-3 px-4">Exit</th>
            <th className="text-right font-normal py-3 px-4">Qty</th>
            <th className="text-left font-normal py-3 px-4">Reason</th>
            <th className="text-right font-normal py-3 px-4">P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {trades.slice(0, 40).map((t, i) => {
            const pos = t.pnl > 0;
            return (
              <tr key={i} className="divider-b hover:bg-[var(--color-surface-1)]/60 transition-colors">
                <td className="py-3 px-4 text-[var(--color-ink-muted)]">
                  {fmtDate(t.date)}
                </td>
                <td className="py-3 px-4 font-medium">{t.symbol}</td>
                <td className="py-3 px-4">
                  <span
                    className={
                      t.side === "CE"
                        ? "text-[var(--color-positive)]"
                        : "text-[var(--color-negative)]"
                    }
                  >
                    {t.side}
                  </span>
                </td>
                <td className="py-3 px-4 text-right">{t.entryPrice.toFixed(2)}</td>
                <td className="py-3 px-4 text-right">{t.exitPrice.toFixed(2)}</td>
                <td className="py-3 px-4 text-right text-[var(--color-ink-muted)]">
                  {t.qty}
                </td>
                <td className="py-3 px-4 text-[13px] text-[var(--color-ink-muted)]">
                  {reasonLabel[t.reason]}
                </td>
                <td
                  className={`py-3 px-4 text-right font-medium ${
                    pos ? "text-[var(--color-positive)]" : "text-[var(--color-negative)]"
                  }`}
                >
                  {fmtINR(t.pnl, { sign: true })}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {trades.length > 40 && (
        <div className="py-4 px-4 text-[13px] text-[var(--color-ink-muted)]">
          Showing 40 of {trades.length} trades.{" "}
          <a href="#" className="text-[var(--color-primary)] hover:underline">
            Download full log (CSV)
          </a>
        </div>
      )}
    </div>
  );
}
