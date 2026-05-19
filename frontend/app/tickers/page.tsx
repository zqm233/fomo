"use client";

import { useEffect, useState } from "react";
import { tickersApi, HotTicker } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, TrendingUp, TrendingDown, Flame, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

function formatSparkPrice(value: unknown): [string, string] {
  const n =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : 0;
  return [`$${(Number.isFinite(n) ? n : 0).toFixed(2)}`, ""];
}

// ── Sparkline ──────────────────────────────────────────────────────────────────

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return <div className="w-20 h-8" />;
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <div className="w-20 h-8">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={positive ? "#22c55e" : "#ef4444"}
            strokeWidth={1.5}
            dot={false}
          />
          <Tooltip
            contentStyle={{ fontSize: 11, padding: "2px 6px", background: "#1e1e2e", border: "none", borderRadius: 4 }}
            labelFormatter={() => ""}
            formatter={formatSparkPrice}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Ticker card ────────────────────────────────────────────────────────────────

function TickerCard({ ticker, rank }: { ticker: HotTicker; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const positive = (ticker.change_pct ?? 0) >= 0;

  return (
    <Card className="bg-card border-border">
      <CardContent className="px-4 py-3">
        <div className="flex items-center gap-4">
          <span className={cn(
            "text-lg font-bold w-6 text-center shrink-0",
            rank <= 3 ? "text-amber-400" : "text-muted-foreground/40"
          )}>
            {rank <= 3 ? ["🥇","🥈","🥉"][rank - 1] : rank}
          </span>

          <div className="w-28 shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm">${ticker.ticker}</span>
              {rank <= 5 && <Flame className="h-3 w-3 text-orange-400" />}
            </div>
            {ticker.name && ticker.name !== ticker.ticker && (
              <p className="text-xs text-muted-foreground truncate max-w-[110px]">{ticker.name}</p>
            )}
          </div>

          <div className="w-16 shrink-0 text-center">
            <span className="text-base font-semibold">{ticker.mention_count}</span>
            <p className="text-xs text-muted-foreground">积分</p>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap gap-1">
              {ticker.sources.map((s) => (
                <Badge key={s} variant="secondary" className="text-xs px-1.5 py-0">{s}</Badge>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Sparkline data={ticker.sparkline} positive={positive} />
            {ticker.price != null ? (
              <div className="text-right w-20">
                <p className="text-sm font-medium">${ticker.price.toFixed(2)}</p>
                <p className={cn("text-xs font-medium flex items-center justify-end gap-0.5", positive ? "text-green-400" : "text-red-400")}>
                  {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {positive ? "+" : ""}{ticker.change_pct?.toFixed(2)}%
                </p>
              </div>
            ) : (
              <div className="w-20 text-xs text-muted-foreground text-center">暂无报价</div>
            )}
          </div>

          <button
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {expanded && ticker.articles.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border space-y-2 pl-10">
            {ticker.articles.map((a) => (
              <div key={a.article_id} className="flex items-start gap-2">
                <Badge variant="outline" className="text-xs shrink-0 mt-0.5">{a.source_name}</Badge>
                <p className="text-xs text-muted-foreground leading-relaxed flex-1 line-clamp-2">{a.preview}</p>
                {a.url && (
                  <a href={a.url} target="_blank" rel="noopener noreferrer"
                    className="text-muted-foreground/40 hover:text-primary shrink-0 mt-0.5">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function TickersPage() {
  const [tickers, setTickers] = useState<HotTicker[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    tickersApi
      .hot()
      .then(setTickers)
      .catch((e: unknown) => {
        console.error(e);
        setTickers([]);
        toast.error(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="flex items-center gap-3">
          <Flame className="h-5 w-5 text-orange-400 shrink-0" />
          <div>
            <h1 className="text-xl font-bold">热门股池</h1>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-xl leading-relaxed">
              统计对象为库中 <strong>日常简讯</strong>正文：最近 <strong>N 个美股交易日</strong>（默认 7，NYSE 日历），每位博主对每个标的<strong>每个交易日最多计 1 分</strong>；
              按积分取前若干名（默认 15）。涨跌幅与同 N 的日线一致。盘前/盘后简报会写入快照；本页为打开时即时重算。
            </p>
          </div>
        </div>
        <span className="text-sm text-muted-foreground shrink-0 sm:pt-1">
          {!loading && `共 ${tickers.length} 只`}
        </span>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : tickers.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Flame className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>暂无数据；请确认已有日常简讯入库，且文中含 <code className="text-xs bg-muted px-1 rounded">$标的</code> 或别名词典中的公司名</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tickers.map((t, i) => (
            <TickerCard key={t.ticker} ticker={t} rank={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
