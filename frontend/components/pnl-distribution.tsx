"use client";

import type { Trade } from "@/lib/mock-data";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function PnLDistribution({ trades }: { trades: Trade[] }) {
  const pnls = trades.map((t) => t.pnl);
  const min = Math.min(...pnls);
  const max = Math.max(...pnls);
  const bins = 14;
  const step = (max - min) / bins;
  const buckets = Array.from({ length: bins }, (_, i) => ({
    range: Math.round(min + i * step + step / 2),
    count: 0,
  }));
  for (const p of pnls) {
    const idx = Math.min(Math.floor((p - min) / step), bins - 1);
    buckets[idx].count += 1;
  }
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={buckets} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="#D8D4CC" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="range"
            tick={{ fill: "#6B6B63", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#D8D4CC" }}
            tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
          />
          <YAxis
            tick={{ fill: "#6B6B63", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "#FAF9F7",
              border: "1px solid #D8D4CC",
              borderRadius: 8,
              fontSize: 13,
            }}
            formatter={(v: number) => [`${v} trades`, "Count"]}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {buckets.map((b, i) => (
              <Cell
                key={i}
                fill={b.range >= 0 ? "#4A7C4E" : "#B04A2E"}
                fillOpacity={0.72}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
