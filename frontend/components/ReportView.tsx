"use client";

import { Report } from "@/lib/api";
import { SentimentChart } from "./SentimentChart";
import { StockPriceBadge } from "./StockPriceBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Hash, Users, Zap, Flame } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Props {
  report: Report;
}

export function ReportView({ report }: Props) {
  const stockEntries = Object.values(report.stock_prices);
  const themes = report.hotspots.themes ?? [];
  const keywords = report.hotspots.keywords ?? [];
  const hotTickers = report.hotspots.hot_tickers ?? [];
  const bloggerOps = report.sentiment.source_sentiments ?? [];

  const hotPool = report.hot_pool ?? [];

  return (
    <div className="space-y-4">
      {/* 简报保存瞬间的热门股池（与「热门股」页同算法） */}
      {hotPool.length > 0 && (
        <Card className="bg-card border-border border-orange-500/20">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-400" />
              本简报生成时的热门股池快照
            </CardTitle>
            <p className="text-xs text-muted-foreground font-normal mt-1">
              与侧栏「热门股」页同一套算法（最近 N 个美股交易日，按简讯归属到 NYSE 会话日计分）；盘前/盘后简报成功保存时写入快照。
            </p>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex flex-wrap gap-2">
              {hotPool.map((h) => (
                <Badge
                  key={h.ticker}
                  variant="secondary"
                  className="text-xs font-mono gap-1.5"
                  title={h.sources?.join("、")}
                >
                  <span className="text-muted-foreground">{h.mention_count}</span>
                  ${h.ticker}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stock prices row */}
      {stockEntries.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {stockEntries.slice(0, 8).map((s) => (
            <StockPriceBadge key={s.symbol} stock={s} />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sentiment */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm text-muted-foreground">市场情绪</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <SentimentChart sentiment={report.sentiment} />
          </CardContent>
        </Card>

        {/* Hot topics */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm text-muted-foreground">热点主题</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {themes.slice(0, 5).map((t, i) => (
              <div key={i} className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <Zap className="h-3 w-3 text-accent shrink-0" />
                  <span className="text-sm font-medium">{t.name}</span>
                  {t.mentions > 0 && (
                    <Badge variant="secondary" className="ml-auto text-xs py-0">
                      {t.mentions}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground pl-5">{t.description}</p>
              </div>
            ))}
            {themes.length === 0 && (
              <p className="text-xs text-muted-foreground">暂无热点</p>
            )}
          </CardContent>
        </Card>

        {/* Keywords & tickers */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-sm text-muted-foreground">关键词 & 标的</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1">
                <Hash className="h-3 w-3" /> 热门关键词
              </p>
              <div className="flex flex-wrap gap-1">
                {keywords.slice(0, 12).map((kw) => (
                  <Badge key={kw} variant="secondary" className="text-xs">
                    {kw}
                  </Badge>
                ))}
              </div>
            </div>
            {hotTickers.length > 0 && (
              <div>
                <p className="text-xs text-muted-foreground mb-1.5">热门标的</p>
                <div className="flex flex-wrap gap-1">
                  {hotTickers.slice(0, 8).map((t) => (
                    <Badge
                      key={t.ticker}
                      variant="outline"
                      className="text-xs font-mono border-accent/30 text-accent"
                      title={t.context}
                    >
                      ${t.ticker}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 仅展示情绪 Agent 判定「有操作/有观点」的博主（不与全文重复展示简讯原文） */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
            <Users className="h-4 w-4 text-accent" />
            今日操作与观点（各博主）
          </CardTitle>
          <p className="text-xs text-muted-foreground font-normal mt-1">
            仅摘录当日具备明确交易操作或可执行观点的数据源；广告、引流、无关内容已过滤。完整简讯请至「文章库」查看。
          </p>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {bloggerOps.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              今日时间窗内未摘录到符合条件的博主级操作或观点。如需阅读原文，请打开「文章库」。
            </p>
          ) : (
            <div className="space-y-3">
              {bloggerOps.map((row) => (
                <div
                  key={row.source}
                  className="rounded-lg border border-border/80 bg-muted/20 px-3 py-2.5 space-y-1.5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{row.source}</span>
                  </div>
                  {row.summary ? (
                    <p className="text-xs text-foreground/90 leading-relaxed">{row.summary}</p>
                  ) : (
                    <p className="text-xs text-muted-foreground">（无摘要）</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary markdown */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-sm text-muted-foreground">AI 简报全文</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <ScrollArea className="max-h-[500px]">
            <div className="prose prose-sm max-w-none dark:prose-invert
              prose-headings:text-primary prose-headings:font-semibold
              prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
              prose-p:text-sm prose-p:leading-relaxed prose-p:my-1
              prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5
              prose-strong:text-foreground">
              <ReactMarkdown>{report.summary_text || "暂无简报内容"}</ReactMarkdown>
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
