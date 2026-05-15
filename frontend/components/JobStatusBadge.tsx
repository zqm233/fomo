"use client";

import { JobStatus } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";

const STATUS_MAP: Record<string, { label: string; variant: "outline" | "destructive" | "secondary" | "default"; spin?: boolean; green?: boolean }> = {
  queued: { label: "排队中", variant: "outline" },
  running: { label: "运行中", variant: "outline", spin: true },
  success: { label: "已完成", variant: "outline", green: true },
  failed: { label: "失败", variant: "destructive" },
};

interface Props {
  status: JobStatus | null;
  isPolling: boolean;
}

export function JobStatusBadge({ status, isPolling }: Props) {
  if (!status && !isPolling) return null;
  if (!status) {
    return (
      <Badge variant="outline" className="text-muted-foreground gap-1">
        <Loader2 className="h-3 w-3 animate-spin" />
        启动中…
      </Badge>
    );
  }

  const conf = STATUS_MAP[status.status] ?? STATUS_MAP.queued;

  return (
    <div className="flex items-center gap-2">
      <Badge
        variant={conf.variant}
        className={
          conf.green
            ? "border-green-500/50 text-green-400 gap-1"
            : conf.spin
            ? "text-yellow-400 border-yellow-500/30 gap-1"
            : ""
        }
      >
        {conf.spin && <Loader2 className="h-3 w-3 animate-spin" />}
        {conf.label}
      </Badge>
      {status.articles_crawled > 0 && (
        <span className="text-xs text-muted-foreground">
          新增 {status.articles_crawled} 篇
        </span>
      )}
      {status.error_msg && (
        <span className="text-xs text-red-400 truncate max-w-40" title={status.error_msg}>
          {status.error_msg}
        </span>
      )}
    </div>
  );
}
