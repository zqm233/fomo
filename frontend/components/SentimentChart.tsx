"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { SentimentData } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const COLORS = {
  bull: "hsl(142, 71%, 45%)",
  bear: "hsl(0, 72%, 51%)",
  neutral: "hsl(38, 92%, 50%)",
};

function scoreColor(score: number) {
  if (score > 0.2) return "text-green-400";
  if (score < -0.2) return "text-red-400";
  return "text-yellow-400";
}

interface Props {
  sentiment: SentimentData;
}

export function SentimentChart({ sentiment }: Props) {
  const chartData = [
    { name: "看多", value: Math.round(sentiment.bull_ratio * 100) },
    { name: "看空", value: Math.round(sentiment.bear_ratio * 100) },
    { name: "中性", value: Math.max(0, 100 - Math.round(sentiment.bull_ratio * 100) - Math.round(sentiment.bear_ratio * 100)) },
  ];

  const labelBg =
    sentiment.overall_score > 0.2
      ? "bg-green-500/10 text-green-400 border-green-500/30"
      : sentiment.overall_score < -0.2
      ? "bg-red-500/10 text-red-400 border-red-500/30"
      : "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className={cn("text-2xl font-bold", scoreColor(sentiment.overall_score))}>
          {sentiment.overall_score > 0 ? "+" : ""}
          {sentiment.overall_score.toFixed(2)}
        </span>
        <Badge variant="outline" className={labelBg}>
          {sentiment.label}
        </Badge>
      </div>

      <ResponsiveContainer width="100%" height={140}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={40}
            outerRadius={60}
            dataKey="value"
            strokeWidth={0}
          >
            <Cell fill={COLORS.bull} />
            <Cell fill={COLORS.bear} />
            <Cell fill={COLORS.neutral} />
          </Pie>
          <Tooltip
            contentStyle={{
              background: "hsl(222, 47%, 9%)",
              border: "1px solid hsl(222, 47%, 16%)",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            formatter={(v) => [`${v}%`]}
          />
        </PieChart>
      </ResponsiveContainer>

      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          看多 {Math.round(sentiment.bull_ratio * 100)}%
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          看空 {Math.round(sentiment.bear_ratio * 100)}%
        </span>
      </div>

      {sentiment.key_reasons.length > 0 && (
        <ul className="text-xs text-muted-foreground space-y-1">
          {sentiment.key_reasons.map((r, i) => (
            <li key={i} className="flex gap-1">
              <span className="text-primary">•</span> {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
