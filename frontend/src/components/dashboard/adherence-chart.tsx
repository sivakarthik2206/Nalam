"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TrendPoint } from "@/lib/types";
import { formatDate } from "@/lib/utils";

interface AdherenceChartProps {
  data?: TrendPoint[];
  isLoading?: boolean;
}

export function AdherenceChart({ data = [], isLoading }: AdherenceChartProps) {
  // If data is empty or loading, show placeholder or skeleton
  const chartData = data.map((d) => ({
    ...d,
    formattedDate: formatDate(d.date, "MMM d"),
  }));

  return (
    <Card className="bg-white border-slate-200 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base sm:text-lg font-bold text-slate-900">
              Adherence Trend (Last 14 Days)
            </CardTitle>
            <CardDescription className="text-xs text-slate-500">
              Aggregated daily medication adherence percentage across all monitored patients
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
            <span className="text-xs font-semibold text-slate-700">Adherence %</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {isLoading ? (
          <div className="h-64 flex items-center justify-center bg-slate-50/50 rounded-lg animate-pulse">
            <p className="text-sm text-slate-400">Loading trend telemetry...</p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
            <p className="text-sm font-medium text-slate-600">No adherence records yet</p>
            <p className="text-xs text-slate-400 mt-1">
              Data points appear once automated calls begin logging responses.
            </p>
          </div>
        ) : (
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="adherenceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#059669" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#059669" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="formattedDate"
                  tickLine={false}
                  axisLine={{ stroke: "#e2e8f0" }}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                />
                <YAxis
                  domain={[0, 100]}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#64748b", fontSize: 11 }}
                  tickFormatter={(val) => `${val}%`}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload as TrendPoint & { formattedDate: string };
                      return (
                        <div className="bg-slate-900 text-white px-3 py-2 rounded-lg text-xs shadow-xl border border-slate-700 space-y-1">
                          <p className="font-semibold text-slate-200">{item.formattedDate}</p>
                          <p className="text-emerald-400 font-bold text-sm">
                            Score: {item.score}%
                          </p>
                          {item.doses_taken !== undefined && item.doses_expected !== undefined && (
                            <p className="text-slate-400 text-[11px]">
                              {item.doses_taken} of {item.doses_expected} doses taken
                            </p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#059669"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#adherenceGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
