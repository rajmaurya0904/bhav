// Realistic mock data derived from the shape ORB v1 actually produces.
// Replace with a FastAPI fetch (/api/runs/[id]) when the backend is wired.

export type Trade = {
  date: string;
  entryTime: string;
  exitTime: string;
  symbol: string;
  side: "CE" | "PE";
  strike: number;
  qty: number;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  reason: "tgt_hit" | "sl_hit" | "trail_sl" | "eod_square_off";
};

export type Metrics = {
  startingCapital: number;
  endingEquity: number;
  totalReturnPct: number;
  cagrPct: number;
  sharpe: number;
  sortino: number;
  maxDrawdownPct: number;
  maxDrawdownAmount: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRatePct: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  expectancy: number;
  totalCosts: number;
  exposureTimePct: number;
};

export type EquityPoint = { t: string; equity: number; drawdown: number };

export type BacktestRun = {
  id: string;
  strategyName: string;
  underlying: string;
  start: string;
  end: string;
  createdAt: string;
  status: "completed" | "running" | "failed";
  metrics: Metrics;
  equity: EquityPoint[];
  trades: Trade[];
};

function seedRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function generateEquity(days: number, startCapital: number, seed: number): EquityPoint[] {
  const rand = seedRandom(seed);
  const points: EquityPoint[] = [];
  let equity = startCapital;
  let peak = equity;
  const base = new Date("2025-08-01");
  for (let i = 0; i < days; i++) {
    const dailyRet = (rand() - 0.45) * 0.018;
    equity = equity * (1 + dailyRet);
    peak = Math.max(peak, equity);
    const drawdown = ((equity - peak) / peak) * 100;
    const d = new Date(base);
    d.setDate(d.getDate() + i);
    points.push({
      t: d.toISOString().slice(0, 10),
      equity: Math.round(equity),
      drawdown,
    });
  }
  return points;
}

function generateTrades(count: number, seed: number): Trade[] {
  const rand = seedRandom(seed);
  const trades: Trade[] = [];
  const base = new Date("2025-08-01");
  for (let i = 0; i < count; i++) {
    const d = new Date(base);
    d.setDate(d.getDate() + Math.floor(i * 1.8));
    const isWin = rand() > 0.42;
    const side: "CE" | "PE" = rand() > 0.5 ? "CE" : "PE";
    const strike = 24000 + Math.floor(rand() * 30) * 50;
    const entryPrice = 60 + rand() * 180;
    const exitMult = isWin ? 1 + rand() * 0.55 : 1 - rand() * 0.32;
    const exitPrice = Number((entryPrice * exitMult).toFixed(2));
    const qty = 75;
    const pnl = Math.round((exitPrice - entryPrice) * qty);
    trades.push({
      date: d.toISOString().slice(0, 10),
      entryTime: `${9 + Math.floor(rand() * 2)}:${30 + Math.floor(rand() * 29)}`
        .padStart(5, "0"),
      exitTime: `${10 + Math.floor(rand() * 2)}:${Math.floor(rand() * 59)}`
        .padStart(5, "0"),
      symbol: `NIFTY${strike}${side}`,
      side,
      strike,
      qty,
      entryPrice: Number(entryPrice.toFixed(2)),
      exitPrice,
      pnl,
      reason: isWin
        ? rand() > 0.5
          ? "tgt_hit"
          : "trail_sl"
        : rand() > 0.5
        ? "sl_hit"
        : "eod_square_off",
    });
  }
  return trades;
}

export function getMockRun(id: string = "orb_2025q3"): BacktestRun {
  const equity = generateEquity(210, 500_000, 42);
  const trades = generateTrades(87, 137);
  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const grossWin = wins.reduce((a, t) => a + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((a, t) => a + t.pnl, 0));
  const ending = equity[equity.length - 1].equity;
  const maxDD = Math.min(...equity.map((p) => p.drawdown));
  const metrics: Metrics = {
    startingCapital: 500_000,
    endingEquity: ending,
    totalReturnPct: ((ending - 500_000) / 500_000) * 100,
    cagrPct: 34.2,
    sharpe: 1.42,
    sortino: 2.08,
    maxDrawdownPct: maxDD,
    maxDrawdownAmount: 500_000 * (maxDD / 100),
    totalTrades: trades.length,
    winningTrades: wins.length,
    losingTrades: losses.length,
    winRatePct: (wins.length / trades.length) * 100,
    avgWin: grossWin / wins.length,
    avgLoss: -grossLoss / losses.length,
    profitFactor: grossWin / grossLoss,
    expectancy: (grossWin - grossLoss) / trades.length,
    totalCosts: 24_650,
    exposureTimePct: 18.4,
  };
  return {
    id,
    strategyName: "orb_v1 (FADE)",
    underlying: "NIFTY 50",
    start: "2025-08-01",
    end: "2026-02-27",
    createdAt: "2026-07-04T09:12:00+05:30",
    status: "completed",
    metrics,
    equity,
    trades,
  };
}

export function getMockRunList(): Pick<
  BacktestRun,
  "id" | "strategyName" | "underlying" | "start" | "end" | "createdAt" | "status"
>[] & { totalReturnPct: number; trades: number; sharpe: number }[] {
  return [
    {
      id: "orb_2025q3",
      strategyName: "orb_v1 (FADE)",
      underlying: "NIFTY 50",
      start: "2025-08-01",
      end: "2026-02-27",
      createdAt: "2026-07-04T09:12:00+05:30",
      status: "completed" as const,
      totalReturnPct: 21.4,
      trades: 87,
      sharpe: 1.42,
    },
    {
      id: "atm_straddle_short",
      strategyName: "atm_straddle_sell",
      underlying: "NIFTY 50",
      start: "2024-11-01",
      end: "2025-06-30",
      createdAt: "2026-07-02T18:41:00+05:30",
      status: "completed" as const,
      totalReturnPct: -4.8,
      trades: 34,
      sharpe: -0.31,
    },
    {
      id: "orb_breakout_v2",
      strategyName: "orb_v1 (BREAKOUT)",
      underlying: "NIFTY 50",
      start: "2025-01-01",
      end: "2026-06-30",
      createdAt: "2026-06-29T22:05:00+05:30",
      status: "completed" as const,
      totalReturnPct: 12.9,
      trades: 142,
      sharpe: 0.87,
    },
  ] as any;
}
