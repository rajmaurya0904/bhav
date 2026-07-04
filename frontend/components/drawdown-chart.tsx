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
import { fmtPct } from "@/lib/format";

export function DrawdownChart({ data }: { data: EquityPoint[] }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#B04A2E" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#B04A2E" stopOpacity={0.25} />
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
            width={54}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            domain={["dataMin - 1", 0]}
          />
          <Tooltip
            contentStyle={{
              background: "#FAF9F7",
              border: "1px solid #D8D4CC",
              borderRadius: 8,
              fontSize: 13,
            }}
            formatter={(v: number) => [fmtPct(v), "Drawdown"]}
          />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#B04A2E"
            strokeWidth={1.25}
            fill="url(#ddFill)"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
