export function fmtINR(n: number, opts: { sign?: boolean } = {}): string {
  const abs = Math.abs(n);
  const formatted =
    abs >= 1e7
      ? `${(abs / 1e7).toFixed(2)} Cr`
      : abs >= 1e5
      ? `${(abs / 1e5).toFixed(2)} L`
      : abs >= 1e3
      ? abs.toLocaleString("en-IN", { maximumFractionDigits: 0 })
      : abs.toFixed(2);
  const s = n < 0 ? `-Rs ${formatted}` : `Rs ${formatted}`;
  if (opts.sign && n > 0) return `+${s}`;
  return s;
}

export function fmtPct(n: number, decimals = 2, opts: { sign?: boolean } = {}): string {
  const s = `${n.toFixed(decimals)}%`;
  if (opts.sign && n > 0) return `+${s}`;
  return s;
}

export function fmtDate(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function fmtTime(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
