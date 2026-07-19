"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import {
  createRun,
  API_BASE,
  aiStatus,
  generateStrategy,
  type GenerateResult,
} from "@/lib/api";
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
  const [dataSource, setDataSource] = useState<"upstox" | "excel">("upstox");
  const [claudeReady, setClaudeReady] = useState(false);
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genResult, setGenResult] = useState<GenerateResult | null>(null);

  useEffect(() => {
    aiStatus().then((s) => setClaudeReady(s.claude_available));
  }, []);

  async function runGenerate() {
    setGenError(null);
    setGenResult(null);
    if (!description.trim()) {
      setGenError("Describe your strategy first");
      return;
    }
    setGenerating(true);
    try {
      const result = await generateStrategy(description);
      setGenResult(result);
      // Attach the generated code as the strategy file so the form below is ready.
      const fname = `${result.name ?? "strategy"}.py`;
      setFile(new File([result.code], fname, { type: "text/x-python" }));
    } catch (err) {
      setGenError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

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
    <div className="min-h-[100dvh] flex flex-col">
      <Nav />
      <main className="flex-1 mx-auto max-w-[900px] px-6 pt-12 pb-24 w-full">
        <h1 className="text-[42px] tracking-[-0.03em] font-medium leading-[1.05]">
          Run a backtest
        </h1>
        <p className="mt-3 text-[16px] leading-[1.6] text-[var(--color-ink-muted)] max-w-[640px]">
          Upload a strategy file, set the range and capital, submit. The engine
          fetches historical candles from Upstox, simulates bar by bar, and
          writes deterministic Parquet results.
        </p>

        <section className="mt-10 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/[0.03] overflow-hidden">
          <div className="px-6 py-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[16px] font-medium flex items-center gap-2">
                  Generate with Claude
                  <span
                    className={
                      "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium " +
                      (claudeReady
                        ? "bg-[var(--color-positive)]/10 text-[var(--color-positive)]"
                        : "bg-[var(--color-ink-muted)]/10 text-[var(--color-ink-muted)]")
                    }
                  >
                    <span
                      className={
                        "h-1.5 w-1.5 rounded-full " +
                        (claudeReady
                          ? "bg-[var(--color-positive)]"
                          : "bg-[var(--color-ink-muted)]")
                      }
                    />
                    {claudeReady ? "CLI connected" : "CLI not detected"}
                  </span>
                </div>
                <div className="mt-1 text-[13px] text-[var(--color-ink-muted)] max-w-[560px]">
                  Describe your idea in plain English. This drives the local{" "}
                  <code className="font-mono text-[12px]">claude</code> CLI on the
                  server — no API key needed. The generated file is validated and
                  auto-attached below.
                </div>
              </div>
            </div>

            {!claudeReady && (
              <p className="mt-4 text-[12.5px] text-[var(--color-ink-muted)] leading-relaxed">
                The <code className="font-mono">claude</code> CLI was not found on
                the backend. Install Claude Code and run{" "}
                <code className="font-mono">claude</code> once to sign in, then
                reload. You can still copy the prompt below and paste it into any
                chat manually.
              </p>
            )}

            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={!claudeReady || generating}
              rows={4}
              placeholder="e.g. At 09:20 sell one ATM straddle (CE + PE). Exit both legs if combined premium loss hits 30%. Otherwise hold until the engine squares off at 15:15."
              className="mt-4 w-full rounded-md border border-[var(--color-border-warm)] bg-white px-4 py-3 text-[14px] font-mono leading-[1.5] outline-none focus:border-[var(--color-primary)] disabled:opacity-50 resize-y"
            />

            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={runGenerate}
                disabled={!claudeReady || generating}
                className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-[13px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {generating ? "Generating…" : "Generate strategy"}
              </button>
              {generating && (
                <span className="text-[12px] text-[var(--color-ink-muted)]">
                  Driving the claude CLI — this can take 10–60s.
                </span>
              )}
            </div>

            {genError && (
              <div className="mt-3 rounded-md border border-[var(--color-negative)]/40 bg-[var(--color-negative)]/5 px-4 py-3 text-[13px] text-[var(--color-negative)]">
                {genError}
              </div>
            )}

            {genResult && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
                    Generated: {genResult.name ?? "strategy"}.py — attached below
                  </span>
                  {genResult.valid ? (
                    <span className="text-[12px] text-[var(--color-positive)]">
                      ✓ passed validation
                    </span>
                  ) : (
                    <span className="text-[12px] text-[var(--color-negative)]">
                      ⚠ validation warnings
                    </span>
                  )}
                </div>
                {!genResult.valid && (
                  <ul className="mb-2 rounded-md border border-[var(--color-negative)]/40 bg-[var(--color-negative)]/5 px-4 py-2 text-[12px] text-[var(--color-negative)] list-disc list-inside">
                    {genResult.violations.map((v, i) => (
                      <li key={i}>{v}</li>
                    ))}
                  </ul>
                )}
                <pre className="max-h-[360px] overflow-auto rounded-md bg-[var(--color-code-bg)] p-4 text-[12.5px] leading-[1.55] font-mono whitespace-pre-wrap">
                  {genResult.code}
                </pre>
                <p className="mt-2 text-[12px] text-[var(--color-ink-muted)]">
                  Read it before you run it. AI code is fast to trust and easy to
                  get subtly wrong.
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-lg border border-[var(--color-border-warm)] bg-white/40 overflow-hidden">
          <details className="group">
            <summary className="flex items-center justify-between cursor-pointer px-6 py-5 hover:bg-[var(--color-surface-1)]/50 transition-colors">
              <div>
                <div className="text-[16px] font-medium">
                  Or copy the prompt for another AI
                </div>
                <div className="mt-1 text-[13px] text-[var(--color-ink-muted)]">
                  No CLI? Copy this prompt into ChatGPT, Claude, or Gemini and
                  describe your idea. The model returns a valid strategy .py you
                  can upload below.
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
            label="Data source"
            hint={
              dataSource === "excel"
                ? "Bundled 1-year NIFTY 50 sample (Jul 2025-Jun 2026), spot + daily ATM CE/PE. No token needed. NIFTY only, ATM only (strike offsets are ignored)."
                : "Live Upstox historical + expired-instruments API. Needs a fresh access token below."
            }
          >
            <select
              name="data_source"
              className="input"
              value={dataSource}
              onChange={(e) => {
                const v = e.target.value as "upstox" | "excel";
                setDataSource(v);
                if (v === "excel") {
                  setUnderlying(UNDERLYINGS[0].key);
                  setLotSize(UNDERLYINGS[0].lot_size);
                }
              }}
            >
              <option value="upstox">Upstox (live API, your token)</option>
              <option value="excel">Sample data (offline, no token)</option>
            </select>
          </Field>

          <Field
            label="Underlying"
            hint={
              dataSource === "excel"
                ? "Sample data only covers NIFTY 50."
                : "Lot size auto-fills from the latest NSE/BSE spec below. You can override it."
            }
          >
            <select
              name="underlying"
              className="input"
              value={underlying}
              disabled={dataSource === "excel"}
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
            label="Warmup days"
            hint="Trading days before the start date fed to the strategy so lookback indicators (S/R, moving averages, opening range history) can seed. No trades are placed during warmup. Set to your longest lookback (e.g. 3 for a 3-day S/R strategy)."
          >
            <input
              name="warmup_days"
              type="number"
              className="input tabular"
              defaultValue={0}
              min={0}
              max={30}
            />
          </Field>

          {dataSource === "upstox" && (
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
          )}

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
      <Footer />
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
