export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RunSummary = {
  id: string;
  strategy_name?: string;
  created_at?: string;
  status: "queued" | "running" | "completed" | "failed" | "unknown";
  error?: string;
  total_return_pct?: number;
  sharpe?: number;
  total_trades?: number;
  win_rate_pct?: number;
  config?: {
    start?: string;
    end?: string;
    capital?: number;
    lot_size?: number;
    underlying?: string;
  };
};

export type EquityPoint = { t: string; equity: number };

export type Trade = {
  symbol: string;
  entry_time: string;
  exit_time: string;
  qty: number;
  entry_price: number;
  exit_price: number;
  pnl_gross: number;
  costs: number;
  pnl_net: number;
  reason: string;
};

export type Metrics = {
  starting_capital: number;
  ending_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  sharpe: number;
  sortino: number | null;
  max_drawdown_pct: number;
  max_drawdown_amount: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  expectancy: number;
  total_costs: number;
  exposure_time_pct: number;
};

export type RunDetail = {
  id: string;
  manifest?: {
    strategy: string;
    config: Record<string, unknown>;
    created_at: string;
  };
  status: { status: string; progress?: string; error?: string };
  metrics?: Metrics;
  equity_curve?: EquityPoint[];
  trades?: Trade[];
};

export async function listRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_BASE}/api/runs`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /api/runs failed: ${res.status}`);
  return res.json();
}

export async function getRun(id: string): Promise<RunDetail> {
  const res = await fetch(`${API_BASE}/api/runs/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /api/runs/${id} failed: ${res.status}`);
  return res.json();
}

export async function createRun(form: FormData): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/runs`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST /api/runs failed: ${res.status} ${text}`);
  }
  return res.json();
}

export function withDrawdown(points: EquityPoint[]): (EquityPoint & { drawdown: number })[] {
  let peak = -Infinity;
  return points.map((p) => {
    peak = Math.max(peak, p.equity);
    const drawdown = peak > 0 ? ((p.equity - peak) / peak) * 100 : 0;
    return { ...p, drawdown };
  });
}
