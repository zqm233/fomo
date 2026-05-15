"use client";

import { useEffect, useState } from "react";
import { reportsApi, Report } from "@/lib/api";
import { ReportView } from "@/components/ReportView";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sun } from "lucide-react";

export default function PreMarketPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    reportsApi
      .latest("pre")
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Sun className="h-5 w-5 text-accent" />
        <h1 className="text-xl font-bold">盘前简讯</h1>
        {report && (
          <Badge variant="outline" className="text-xs">
            {report.report_date}
          </Badge>
        )}
        <Badge variant="secondary" className="text-xs ml-auto">
          美东 08:30 自动更新
        </Badge>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" />
          加载中…
        </div>
      )}

      {error && (
        <div className="text-sm text-red-400 text-center py-12">
          {error.includes("404") ? "今日尚无盘前简报，请等待定时任务运行或手动触发。" : error}
        </div>
      )}

      {report && <ReportView report={report} />}
    </div>
  );
}
