"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/mock-data";
import { fmtINR } from "@/lib/format";

export function EquityCurve({ data }: { data: EquityPoint[] }) {
  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#C2522D" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#C2522D" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#D8D4CC" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fill: "#6B6B63", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#D8D4CC" }}
            minTickGap={40}
          />
          <YAxis
            tick={{ fill: "#6B6B63", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={72}
            tickFormatter={(v) => `${(v / 1e5).toFixed(1)}L`}
            domain={["dataMin - 5000", "dataMax + 5000"]}
          />
          <Tooltip
            contentStyle={{
              background: "#FAF9F7",
              border: "1px solid #D8D4CC",
              borderRadius: 8,
              fontSize: 13,
              boxShadow: "0 4px 24px rgba(26,26,24,0.08)",
            }}
            labelStyle={{ color: "#1A1A18", fontWeight: 500 }}
            itemStyle={{ color: "#1A1A18" }}
            formatter={(v: number) => [fmtINR(v), "Equity"]}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#C2522D"
            strokeWidth={1.5}
            fill="url(#equityFill)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
