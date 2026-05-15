"use client";

import { Report } from "@/lib/api";
import { SentimentChart } from "./SentimentChart";
import { StockPriceBadge } from "./StockPriceBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Hash, Zap } from "lucide-react";

interface Props {
  report: Report;
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="prose-report space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith("## ")) {
          return <h2 key={i}>{line.slice(3)}</h2>;
        }
        if (line.startsWith("### ")) {
          return <h3 key={i}>{line.slice(4)}</h3>;
        }
        if (line.startsWith("- ") || line.startsWith("* ")) {
          return <p key={i} className="pl-4 before:content-['•'] before:mr-2 before:text-primary">{line.slice(2)}</p>;
        }
        if (line.startsWith("**") && line.endsWith("**")) {
          return <p key={i} className="font-semibold text-foreground">{line.slice(2, -2)}</p>;
        }
        if (line.trim() === "") {
          return <div key={i} className="h-2" />;
        }
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

export function ReportView({ report }: Props) {
  const stockEntries = Object.values(report.stock_prices);
  const themes = report.hotspots.themes ?? [];
  const keywords = report.hotspots.keywords ?? [];
  const hotTickers = report.hotspots.hot_tickers ?? [];

  return (
    <div className="space-y-4">
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

      {/* Summary markdown */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-sm text-muted-foreground">AI 简报全文</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <ScrollArea className="max-h-[500px]">
            <MarkdownText text={report.summary_text || "暂无简报内容"} />
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
