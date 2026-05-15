"use client";

import { useEffect, useState } from "react";
import { reportsApi, Report } from "@/lib/api";
import { ReportView } from "@/components/ReportView";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, History, Sun, Sunset } from "lucide-react";
import { cn } from "@/lib/utils";

export default function HistoryPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    reportsApi
      .list({ limit: 60 })
      .then((r) => {
        setReports(r);
        if (r.length > 0) setSelected(r[0]);
      })
      .finally(() => setLoading(false));
  }, []);

  const grouped = reports.reduce<Record<string, Report[]>>((acc, r) => {
    if (!acc[r.report_date]) acc[r.report_date] = [];
    acc[r.report_date].push(r);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <History className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">历史简报</h1>
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {!loading && reports.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">暂无历史简报</div>
      )}

      {!loading && reports.length > 0 && (
        <div className="flex gap-4 h-[calc(100vh-10rem)]">
          {/* Left: date list */}
          <div className="w-52 shrink-0 space-y-1 overflow-y-auto pr-1">
            {Object.entries(grouped)
              .sort(([a], [b]) => b.localeCompare(a))
              .map(([date, reps]) => (
                <div key={date} className="space-y-0.5">
                  <p className="text-xs text-muted-foreground px-2 pt-2">{date}</p>
                  {reps.map((r) => (
                    <Card
                      key={r.id}
                      className={cn(
                        "cursor-pointer border transition-colors",
                        selected?.id === r.id
                          ? "border-primary/50 bg-primary/5"
                          : "border-border bg-card hover:border-border/80 hover:bg-muted/30"
                      )}
                      onClick={() => setSelected(r)}
                    >
                      <CardContent className="px-3 py-2 flex items-center gap-2">
                        {r.report_type === "pre" ? (
                          <Sun className="h-3 w-3 text-accent shrink-0" />
                        ) : (
                          <Sunset className="h-3 w-3 text-orange-400 shrink-0" />
                        )}
                        <span className="text-xs">
                          {r.report_type === "pre" ? "盘前" : "盘后"}
                        </span>
                        <Badge variant="secondary" className="text-xs ml-auto py-0">
                          {r.article_count}
                        </Badge>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ))}
          </div>

          {/* Right: report detail */}
          <div className="flex-1 overflow-y-auto">
            {selected ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  {selected.report_type === "pre" ? (
                    <Sun className="h-4 w-4 text-accent" />
                  ) : (
                    <Sunset className="h-4 w-4 text-orange-400" />
                  )}
                  <h2 className="font-semibold">
                    {selected.report_date} ·{" "}
                    {selected.report_type === "pre" ? "盘前简讯" : "盘后复盘"}
                  </h2>
                  <Badge variant="outline" className="text-xs ml-auto">
                    {selected.article_count} 篇文章
                  </Badge>
                </div>
                <ReportView report={selected} />
              </div>
            ) : (
              <div className="text-center py-16 text-muted-foreground">
                从左侧选择一份简报
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
