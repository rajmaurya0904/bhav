type Tone = "neutral" | "positive" | "negative";

export function MetricCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
}) {
  const toneClass =
    tone === "positive"
      ? "text-[var(--color-positive)]"
      : tone === "negative"
      ? "text-[var(--color-negative)]"
      : "text-[var(--color-ink)]";
  return (
    <div className="flex flex-col gap-2 py-5 px-6 divider-t first:border-t-0 md:divider-t md:border-l md:first:border-l-0">
      <div className="text-[12px] uppercase tracking-[0.08em] text-[var(--color-ink-muted)]">
        {label}
      </div>
      <div className={`tabular text-[28px] font-medium tracking-tight ${toneClass}`}>
        {value}
      </div>
      {sub && (
        <div className="tabular text-[13px] text-[var(--color-ink-muted)]">{sub}</div>
      )}
    </div>
  );
}
