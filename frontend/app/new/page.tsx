import { Nav } from "@/components/nav";

export default function NewBacktestPage() {
  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[720px] px-6 pt-16 pb-24">
        <h1 className="text-[42px] tracking-[-0.03em] font-medium leading-[1.05]">
          Configure a backtest
        </h1>
        <p className="mt-4 text-[17px] leading-[1.6] text-[var(--color-ink-muted)]">
          Point the engine at a strategy file, a date range, and a starting
          capital. Results land in the runs list when the job completes.
        </p>

        <form className="mt-12 space-y-8">
          <Field
            label="Strategy file"
            hint="Path to a Python file exposing `strategy = MyStrategy()`"
          >
            <input
              className="input"
              defaultValue="examples/orb_v1.py"
            />
          </Field>

          <div className="grid grid-cols-2 gap-6">
            <Field label="Start date">
              <input type="date" className="input" defaultValue="2025-08-01" />
            </Field>
            <Field label="End date">
              <input type="date" className="input" defaultValue="2026-02-27" />
            </Field>
          </div>

          <Field label="Underlying">
            <select className="input" defaultValue="NIFTY">
              <option value="NIFTY">NIFTY 50</option>
              <option value="BANKNIFTY">BANK NIFTY</option>
              <option value="FINNIFTY">FIN NIFTY</option>
              <option value="MIDCPNIFTY">MIDCAP NIFTY</option>
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-6">
            <Field label="Starting capital (Rs)">
              <input type="number" className="input tabular" defaultValue={500000} />
            </Field>
            <Field label="Lot size">
              <input type="number" className="input tabular" defaultValue={75} />
            </Field>
          </div>

          <Field
            label="Upstox access token"
            hint="Expires daily around 03:30 IST. Regenerate before each run."
          >
            <input type="password" className="input font-mono" placeholder="eyJ0eXAi..." />
          </Field>

          <div className="pt-6 flex items-center gap-3 divider-t">
            <button
              type="button"
              className="rounded-md bg-[var(--color-primary)] px-5 py-2.5 text-[14px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors mt-6"
            >
              Start backtest
            </button>
            <button
              type="button"
              className="rounded-md border border-[var(--color-border-warm)] px-5 py-2.5 text-[14px] font-medium hover:bg-[var(--color-surface-1)] transition-colors mt-6"
            >
              Save as preset
            </button>
          </div>
        </form>

        <style>{`
          .input {
            width: 100%;
            border: 1px solid var(--color-border-warm);
            background: white;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 14px;
            color: var(--color-ink);
            font-family: inherit;
            outline: none;
            transition: border-color 120ms;
          }
          .input:focus {
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(194, 82, 45, 0.12);
          }
        `}</style>
      </main>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-[13px] font-medium text-[var(--color-ink)]">
        {label}
      </label>
      {children}
      {hint && (
        <p className="text-[12px] text-[var(--color-ink-muted)] leading-relaxed">
          {hint}
        </p>
      )}
    </div>
  );
}
