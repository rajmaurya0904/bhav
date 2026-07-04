"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Nav } from "@/components/nav";
import { createRun, API_BASE } from "@/lib/api";
import { AI_PROMPT } from "@/lib/ai-prompt";
import { UNDERLYINGS, lotSizeFor } from "@/lib/underlyings";

export default function NewBacktestPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [underlying, setUnderlying] = useState(UNDERLYINGS[0].key);
  const [lotSize, setLotSize] = useState(UNDERLYINGS[0].lot_size);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("Attach a strategy .py file");
      return;
    }
    const fd = new FormData(e.currentTarget);
    fd.set("strategy", file);
    setSubmitting(true);
    try {
      const { id } = await createRun(fd);
      router.push(`/backtests/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  async function copyPrompt() {
    await navigator.clipboard.writeText(AI_PROMPT);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="min-h-[100dvh]">
      <Nav />
      <main className="mx-auto max-w-[900px] px-6 pt-12 pb-24">
        <h1 className="text-[42px] tracking-[-0.03em] font-medium leading-[1.05]">
          Run a backtest
        </h1>
        <p className="mt-3 text-[16px] leading-[1.6] text-[var(--color-ink-muted)] max-w-[640px]">
          Upload a strategy file, set the range and capital, submit. The engine
          fetches historical candles from Upstox, simulates bar by bar, and
          writes deterministic Parquet results.
        </p>

        <section className="mt-10 rounded-lg border border-[var(--color-border-warm)] bg-white/40 overflow-hidden">
          <details className="group">
            <summary className="flex items-center justify-between cursor-pointer px-6 py-5 hover:bg-[var(--color-surface-1)]/50 transition-colors">
              <div>
                <div className="text-[16px] font-medium">
                  Generate a strategy with AI
                </div>
                <div className="mt-1 text-[13px] text-[var(--color-ink-muted)]">
                  Copy this prompt into ChatGPT, Claude, or Gemini and describe
                  your idea. The model returns a valid strategy .py you can
                  upload below.
                </div>
              </div>
              <span className="text-[13px] text-[var(--color-ink-muted)] group-open:hidden">
                Show
              </span>
              <span className="text-[13px] text-[var(--color-ink-muted)] hidden group-open:inline">
                Hide
              </span>
            </summary>
            <div className="border-t border-[var(--color-border-warm)] p-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
                  System prompt
                </span>
                <button
                  type="button"
                  onClick={copyPrompt}
                  className="rounded-md border border-[var(--color-border-warm)] px-3 py-1.5 text-[13px] font-medium hover:bg-[var(--color-surface-1)] transition-colors"
                >
                  {copied ? "Copied" : "Copy prompt"}
                </button>
              </div>
              <pre className="max-h-[360px] overflow-auto rounded-md bg-[var(--color-code-bg)] p-4 text-[12.5px] leading-[1.55] font-mono whitespace-pre-wrap">
                {AI_PROMPT}
              </pre>
            </div>
          </details>
        </section>

        <form
          onSubmit={onSubmit}
          className="mt-10 rounded-lg border border-[var(--color-border-warm)] bg-white/40 p-8 space-y-7"
        >
          <Field
            label="Strategy file (.py)"
            hint="A Python file that exposes `strategy = MyStrategy()` at module level"
          >
            <label className="flex items-center gap-4 rounded-md border border-dashed border-[var(--color-border-warm)] px-4 py-4 bg-[var(--color-surface-1)]/40 cursor-pointer hover:bg-[var(--color-surface-1)] transition-colors">
              <input
                type="file"
                accept=".py"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
              <span
                className={
                  file
                    ? "text-[14px] font-medium"
                    : "text-[14px] text-[var(--color-ink-muted)]"
                }
              >
                {file ? file.name : "Click to select a .py file"}
              </span>
              {file && (
                <span className="text-[12px] text-[var(--color-ink-muted)] tabular">
                  {(file.size / 1024).toFixed(1)} kb
                </span>
              )}
            </label>
          </Field>

          <div className="grid grid-cols-2 gap-6">
            <Field label="Start date">
              <input
                name="start_date"
                type="date"
                className="input"
                defaultValue="2025-08-01"
                required
              />
            </Field>
            <Field label="End date">
              <input
                name="end_date"
                type="date"
                className="input"
                defaultValue="2025-08-15"
                required
              />
            </Field>
          </div>

          <Field
            label="Underlying"
            hint="Lot size auto-fills from the latest NSE/BSE spec below. You can override it."
          >
            <select
              name="underlying"
              className="input"
              value={underlying}
              onChange={(e) => {
                setUnderlying(e.target.value);
                setLotSize(lotSizeFor(e.target.value));
              }}
            >
              {UNDERLYINGS.map((u) => (
                <option key={u.key} value={u.key}>
                  {u.display} · lot {u.lot_size}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-2 gap-6">
            <Field label="Starting capital (Rs)">
              <input
                name="capital"
                type="number"
                className="input tabular"
                defaultValue={500000}
                min={10000}
                required
              />
            </Field>
            <Field label="Lot size">
              <input
                name="lot_size"
                type="number"
                className="input tabular"
                value={lotSize}
                onChange={(e) => setLotSize(Number(e.target.value))}
                min={1}
                required
              />
            </Field>
          </div>

          <Field
            label="Upstox access token"
            hint="Expires daily around 03:30 IST. Never committed to the runs directory."
          >
            <input
              name="upstox_token"
              type="password"
              className="input font-mono"
              placeholder="eyJ0eXAi..."
              required
            />
          </Field>

          {error && (
            <div className="rounded-md border border-[var(--color-negative)]/40 bg-[var(--color-negative)]/5 px-4 py-3 text-[13px] text-[var(--color-negative)]">
              {error}
            </div>
          )}

          <div className="pt-2 flex items-center gap-3 divider-t">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-[var(--color-primary)] px-5 py-2.5 text-[14px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors mt-6 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Submitting..." : "Start backtest"}
            </button>
            <p className="mt-6 text-[12px] text-[var(--color-ink-muted)]">
              API: {API_BASE}
            </p>
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
