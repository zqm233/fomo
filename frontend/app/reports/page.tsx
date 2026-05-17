"use client";

import { useEffect, useState } from "react";
import { reportsApi, pipelineApi, Report } from "@/lib/api";
import { ReportView } from "@/components/ReportView";
import { useJobPoller } from "@/lib/useJobPoller";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, FileText, Sun, Sunset, Play, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Filter = "all" | "pre" | "post";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all",  label: "全部" },
  { value: "pre",  label: "盘前" },
  { value: "post", label: "盘后" },
];

const TRIGGER_TYPES: { value: "pre" | "post"; label: string }[] = [
  { value: "pre",  label: "盘前简报" },
  { value: "post", label: "盘后简报" },
];

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  const { status: jobStatus, isPolling, startPolling } = useJobPoller();

  // Reload reports when pipeline job completes
  useEffect(() => {
    if (jobStatus?.status === "success") {
      reportsApi
        .list({ limit: 100 })
        .then((r) => {
          setReports(r);
          if (r.length > 0) setSelected(r[0]);
        })
        .catch((e: unknown) => {
          toast.error(e instanceof Error ? e.message : "刷新简报列表失败");
        });
    }
  }, [jobStatus?.status]);

  useEffect(() => {
    reportsApi
      .list({ limit: 100 })
      .then((r) => {
        setReports(r);
        if (r.length > 0) setSelected(r[0]);
      })
      .catch((e: unknown) => {
        toast.error(e instanceof Error ? e.message : "加载简报失败");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleTrigger = async (type: "pre" | "post", skipCrawl = false) => {
    try {
      const { job_id } = await pipelineApi.trigger(type, { skip_crawl: skipCrawl });
      startPolling(job_id);
      toast.success(
        skipCrawl
          ? `${type === "pre" ? "盘前" : "盘后"}简报生成中（不拉新数据，用库内简讯 + 新鲜行情）…`
          : `${type === "pre" ? "盘前" : "盘后"}简报生成中…`
      );
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  const filtered = filter === "all" ? reports : reports.filter((r) => r.report_type === filter);

  const grouped = filtered.reduce<Record<string, Report[]>>((acc, r) => {
    if (!acc[r.report_date]) acc[r.report_date] = [];
    acc[r.report_date].push(r);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <FileText className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">投研简报</h1>
        {/* Filter tabs */}
        <div className="flex gap-1 bg-muted/40 rounded-lg p-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "px-3 py-1 rounded-md text-xs font-medium transition-colors",
                filter === f.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <JobStatusBadge status={jobStatus} isPolling={isPolling} />
          {TRIGGER_TYPES.map((t) => (
            <Button
              key={t.value}
              size="sm"
              variant="outline"
              className="h-7 text-xs gap-1"
              disabled={isPolling}
              onClick={() => handleTrigger(t.value, false)}
            >
              {isPolling
                ? <Loader2 className="h-3 w-3 animate-spin" />
                : <Play className="h-3 w-3" />
              }
              {t.label}
            </Button>
          ))}
          <Button
            size="sm"
            variant="secondary"
            className="h-7 text-xs gap-1"
            title="临时：不抓取 RSS/新推文，只用库里已有简讯；仍会拉取最新股价与盘面数据"
            disabled={isPolling}
            onClick={() => handleTrigger("pre", true)}
          >
            {isPolling ? <Loader2 className="h-3 w-3 animate-spin" /> : <FlaskConical className="h-3 w-3" />}
            盘前(不拉新)
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="h-7 text-xs gap-1"
            title="临时：不抓取 RSS/新推文，只用库里已有简讯；仍会拉取最新股价与盘面数据"
            disabled={isPolling}
            onClick={() => handleTrigger("post", true)}
          >
            {isPolling ? <Loader2 className="h-3 w-3 animate-spin" /> : <FlaskConical className="h-3 w-3" />}
            盘后(不拉新)
          </Button>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {!loading && reports.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          暂无简报，等待定时任务运行或手动触发
        </div>
      )}

      {!loading && reports.length > 0 && (
        <div className="flex gap-4 h-[calc(100vh-10rem)]">
          {/* Left: list */}
          <div className="w-52 shrink-0 space-y-1 overflow-y-auto pr-1">
            {filtered.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8">暂无此类简报</p>
            ) : (
              Object.entries(grouped)
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
                          <Badge variant="secondary" className="text-xs ml-auto py-0" title="本次分析引用的时间窗内简讯条数">
                            {r.article_count} 条简讯
                          </Badge>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ))
            )}
          </div>

          {/* Right: detail */}
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
                    {selected.report_date} · {selected.report_type === "pre" ? "盘前简讯" : "盘后复盘"}
                  </h2>
                  <Badge variant="outline" className="text-xs ml-auto" title="生成这份简报时所依据的时间窗内简讯条数">
                    引用简讯 {selected.article_count} 条
                  </Badge>
                </div>
                <ReportView report={selected} />
              </div>
            ) : (
              <div className="text-center py-16 text-muted-foreground">从左侧选择一份简报</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
