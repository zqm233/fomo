"use client";

import { useEffect, useState, useCallback } from "react";
import { pipelineApi, JobStatus, SourceTask, TaskStep } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity,
  AtSign,
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  RotateCcw,
  Rss,
  Square,
  Trash2,
  XCircle,
} from "lucide-react";

// ── hooks ─────────────────────────────────────────────────────────────────────

function useElapsed(startedAt: string | null): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const tick = () => setElapsed(Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return elapsed;
}

function fmtElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function sourceIcon(type: string) {
  return type === "twitter"
    ? <AtSign className="h-4 w-4 text-sky-400 shrink-0" />
    : <Rss className="h-4 w-4 text-green-400 shrink-0" />;
}

function fmtTime(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

const CN_TZ = "Asia/Shanghai";
const ET_TZ = "America/New_York";

function dateKeyInTz(d: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function fmtTimeInTz(d: Date, timeZone: string) {
  return d.toLocaleTimeString("zh-CN", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function fmtMonthDayInTz(d: Date, timeZone: string) {
  return d.toLocaleDateString("zh-CN", {
    timeZone,
    month: "numeric",
    day: "numeric",
  });
}

function fmtDateTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const cnDateKey = dateKeyInTz(d, CN_TZ);
  const cnTime = fmtTimeInTz(d, CN_TZ);
  const cnDate =
    cnDateKey === dateKeyInTz(today, CN_TZ)
      ? "今天"
      : cnDateKey === dateKeyInTz(tomorrow, CN_TZ)
        ? "明天"
        : fmtMonthDayInTz(d, CN_TZ);
  const etLabel = `${fmtMonthDayInTz(d, ET_TZ)} ${fmtTimeInTz(d, ET_TZ)}`;
  return `${cnDate} ${cnTime}（美东 ${etLabel}）`;
}

/** 流水线任务展示名（与 run_type 一致，不用「手动/自动」字样） */
function pipelineJobTitle(runType: string): string {
  const titles: Record<string, string> = {
    pre: "盘前简报",
    post: "盘后简报",
    manual: "全源数据同步",
    single_sync: "单源数据抓取",
  };
  return titles[runType] ?? runType;
}

// ── StepRow ───────────────────────────────────────────────────────────────────

function StepRow({ step }: { step: TaskStep }) {
  return (
    <div className="flex items-center gap-2 py-1.5 px-4 border-b border-border/50 last:border-0 bg-muted/20">
      <div className="w-3 shrink-0" />
      <div className="w-3.5 flex justify-center shrink-0">
        {step.status === "running"  && <Loader2      className="h-3 w-3 text-primary animate-spin" />}
        {step.status === "pending"  && <Clock        className="h-3 w-3 text-muted-foreground/50" />}
        {step.status === "success"  && <CheckCircle2 className="h-3 w-3 text-green-500" />}
        {step.status === "failed"   && <XCircle      className="h-3 w-3 text-red-500" />}
      </div>
      <span className={`text-xs flex-1 ${
        step.status === "running" ? "text-foreground font-medium" :
        step.status === "failed"  ? "text-red-500" :
        step.status === "success" ? "text-muted-foreground" :
        "text-muted-foreground/50"
      }`}>
        {step.name}
      </span>
      {step.detail && (
        <span className={`text-xs tabular-nums shrink-0 ${
          step.status === "failed" ? "text-red-400" : "text-muted-foreground"
        }`}>
          {step.detail}
        </span>
      )}
    </div>
  );
}

// ── TaskRow ───────────────────────────────────────────────────────────────────

function TaskRow({
  task,
  onRetry,
  onDelete,
  indented = false,
}: {
  task: SourceTask;
  onRetry?: (task: SourceTask) => void;
  onDelete?: (task: SourceTask) => void;
  indented?: boolean;
}) {
  const isRunning = task.status === "running";
  const isPending = task.status === "pending";
  const isSuccess = task.status === "success";
  const isFailed  = task.status === "failed";

  const elapsed = useElapsed(isRunning ? task.started_at : null);
  const isSlowWarning = isRunning && elapsed >= 120;  // 2 min — warn
  const isStuckAlert  = isRunning && elapsed >= 300;  // 5 min — likely stuck

  const hasSteps = task.steps && task.steps.length > 0;

  return (
    <div className={`border-b border-border last:border-0 ${isRunning ? "bg-primary/5" : ""}`}>
      <div className={`group flex items-center gap-3 py-2.5 transition-colors ${indented ? "pl-8 pr-4" : "px-4"}`}>
      {/* Status icon */}
      <div className="w-5 flex justify-center shrink-0">
        {isRunning  && <Loader2      className="h-4 w-4 text-primary animate-spin" />}
        {isPending  && <Clock        className="h-4 w-4 text-muted-foreground" />}
        {isSuccess  && <CheckCircle2 className="h-4 w-4 text-green-500" />}
        {isFailed   && <XCircle      className="h-4 w-4 text-red-500" />}
      </div>

      {/* Source icon + name */}
      {sourceIcon(task.source_type)}
      <div className="flex-1 min-w-0">
        <p className={`text-sm truncate ${isRunning ? "font-medium" : ""}`}>
          {task.source_name}
        </p>
        {/* Progress / warnings */}
        {isRunning && task.error_msg && !isStuckAlert && !isSlowWarning && (
          <p className="text-xs text-primary/80 truncate mt-0.5">{task.error_msg}</p>
        )}
        {isStuckAlert && (
          <p className="text-xs text-red-500 mt-0.5">⚠ 已运行 {fmtElapsed(elapsed)}，可能卡住</p>
        )}
        {isSlowWarning && !isStuckAlert && (
          <p className="text-xs text-amber-500 mt-0.5">
            {task.error_msg || "耗时较长，正在等待响应…"}
          </p>
        )}
        {isFailed && task.error_msg && (
          <p className="text-xs text-red-500 truncate mt-0.5">{task.error_msg}</p>
        )}
      </div>

      {/* Status label */}
      <div className="shrink-0 text-xs tabular-nums">
        {isRunning && (
          <span className={isStuckAlert ? "text-red-500 font-medium" : isSlowWarning ? "text-amber-500" : "text-primary font-medium"}>
            {fmtElapsed(elapsed)}
          </span>
        )}
        {isPending && <span className="text-muted-foreground">等待中</span>}
        {isSuccess && (
          <span className="text-muted-foreground">
            {task.articles_found > 0 ? `+${task.articles_found} 篇` : "无新内容"}
          </span>
        )}
        {isFailed && <span className="text-red-500">失败</span>}
      </div>

      {/* Start time */}
      <span className="text-xs text-muted-foreground w-14 text-right shrink-0 tabular-nums">
        {fmtTime(task.started_at ?? null)}
      </span>

      {/* Actions — show on hover */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        {(isSuccess || isFailed) && onRetry && (
          <button
            onClick={() => onRetry(task)}
            title="重新运行"
            className="h-6 w-6 flex items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
        {(isSuccess || isFailed) && onDelete && (
          <button
            onClick={() => onDelete(task)}
            title="删除记录"
            className="h-6 w-6 flex items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-red-500 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      </div>
      {/* Sub-steps */}
      {hasSteps && (
        <div className={indented ? "ml-8" : "ml-4"}>
          {task.steps.map(step => <StepRow key={step.key} step={step} />)}
        </div>
      )}
    </div>
  );
}

// ── ActiveJobPanel ────────────────────────────────────────────────────────────

function ActiveJobPanel({
  job,
  onRefresh,
}: {
  job: JobStatus;
  onRefresh: () => void;
}) {
  const [tasks, setTasks] = useState<SourceTask[]>([]);
  const [cancelling, setCancelling] = useState(false);

  const fetchTasks = useCallback(async () => {
    try { setTasks(await pipelineApi.jobTasks(job.job_id)); } catch { /* ignore */ }
  }, [job.job_id]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);
  useEffect(() => {
    if (job.status !== "running" && job.status !== "queued") return;
    const id = setInterval(fetchTasks, 5000);
    return () => clearInterval(id);
  }, [job.status, fetchTasks]);

  const done    = tasks.filter(t => t.status === "success" || t.status === "failed").length;
  const total   = tasks.length;
  const running = tasks.find(t => t.status === "running");
  const isActive = job.status === "running" || job.status === "queued";

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await pipelineApi.cancelJob(job.job_id);
      toast.success("取消请求已发送");
      onRefresh();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setCancelling(false);
    }
  };

  const handleRetry = async (task: SourceTask) => {
    try {
      const { message } = await pipelineApi.retryTask(task.id);
      toast.success(message);
      onRefresh();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  const handleDelete = async (task: SourceTask) => {
    try {
      await pipelineApi.deleteTask(task.id);
      setTasks(prev => prev.filter(t => t.id !== task.id));
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {isActive
            ? <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
            : job.status === "success"
              ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
              : <XCircle className="h-4 w-4 text-red-500 shrink-0" />}
          <span className="text-sm font-medium">{pipelineJobTitle(job.run_type)}</span>
          {running && (
            <span className="text-xs text-muted-foreground truncate">· 正在获取 {running.source_name}</span>
          )}
          {isActive && !running && tasks.length > 0 && job.error_msg && (
            <span className="text-xs text-primary/80 truncate">· {job.error_msg}</span>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {total > 0 && (
            <span className="text-xs text-muted-foreground tabular-nums">{done}/{total}</span>
          )}
          <span className="text-xs text-muted-foreground tabular-nums">
            {fmtTime(job.started_at ?? job.created_at)}
          </span>
          {isActive && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-red-500 hover:bg-red-500/10 transition-colors disabled:opacity-50"
            >
              {cancelling ? <Loader2 className="h-3 w-3 animate-spin" /> : <Square className="h-3 w-3" />}
              终止
            </button>
          )}
        </div>
      </div>

      {tasks.length === 0 ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      ) : (
        tasks.map(task => (
          <TaskRow key={task.id} task={task} onRetry={handleRetry} onDelete={handleDelete} />
        ))
      )}
    </div>
  );
}

// ── HistoryJob ────────────────────────────────────────────────────────────────

function HistoryJobRow({ job }: { job: JobStatus }) {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<SourceTask[]>([]);
  const [loaded, setLoaded] = useState(false);

  const loadTasks = useCallback(async () => {
    if (loaded) return;
    try {
      setTasks(await pipelineApi.jobTasks(job.job_id));
      setLoaded(true);
    } catch { /* ignore */ }
  }, [job.job_id, loaded]);

  const toggle = () => {
    if (!open) loadTasks();
    setOpen(v => !v);
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        {job.status === "success"
          ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
          : <XCircle className="h-4 w-4 text-red-500 shrink-0" />}
        <span className="text-sm flex-1 min-w-0 truncate">
          {pipelineJobTitle(job.run_type)}
          {job.articles_crawled > 0 && (
            <span className="text-muted-foreground ml-2">+{job.articles_crawled} 篇</span>
          )}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {fmtTime(job.started_at ?? job.created_at)}
        </span>
      </button>
      {open && tasks.length > 0 && (
        <div className="border-t border-border border-l-2 border-l-border ml-4">
          {tasks.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              indented
              onRetry={async (t) => {
                try {
                  const { message } = await pipelineApi.retryTask(t.id);
                  toast.success(message);
                } catch (e: unknown) { toast.error((e as Error).message); }
              }}
              onDelete={async (t) => {
                try {
                  await pipelineApi.deleteTask(t.id);
                  setTasks(prev => prev.filter(x => x.id !== t.id));
                } catch (e: unknown) { toast.error((e as Error).message); }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── SchedulerPanel ────────────────────────────────────────────────────────────

function SchedulerPanel() {
  const [jobs, setJobs] = useState<Array<{ id: string; name: string; next_run: string | null }>>([]);

  useEffect(() => {
    pipelineApi.schedulerStatus().then(setJobs).catch(() => {});
    const id = setInterval(() => {
      pipelineApi.schedulerStatus().then(setJobs).catch(() => {});
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  if (jobs.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border bg-muted/30">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">计划任务</p>
      </div>
      <div className="divide-y divide-border">
        {jobs.map(job => (
          <div key={job.id} className="flex items-center gap-3 px-4 py-3">
            <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="text-sm flex-1">{job.name}</span>
            <div className="text-right shrink-0">
              <p className="text-xs text-muted-foreground">下次触发</p>
              <p className="text-sm tabular-nums font-medium">
                {fmtDateTime(job.next_run)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await pipelineApi.listJobs(30));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadJobs(); }, [loadJobs]);

  const activeJob  = jobs.find(j => j.status === "running" || j.status === "queued");
  const historyJobs = jobs.filter(j => j.status === "success" || j.status === "failed");

  // poll job list while something is active
  useEffect(() => {
    if (!activeJob) return;
    const id = setInterval(loadJobs, 4000);
    return () => clearInterval(id);
  }, [activeJob, loadJobs]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Activity className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">任务队列</h1>
        {activeJob && (
          <Badge className="text-xs bg-primary/15 text-primary border-primary/30 animate-pulse">
            运行中
          </Badge>
        )}
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" onClick={loadJobs}>
            <RefreshCw className="h-3 w-3 mr-1" />
            刷新
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {/* Scheduled jobs */}
          <SchedulerPanel />

          {/* Active job — tasks shown directly */}
          {activeJob && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">当前任务</p>
              <ActiveJobPanel job={activeJob} onRefresh={loadJobs} />
            </div>
          )}

          {/* History */}
          {historyJobs.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">历史记录</p>
              <div className="space-y-2">
                {historyJobs.map(job => (
                  <HistoryJobRow key={job.job_id} job={job} />
                ))}
              </div>
            </div>
          )}

          {/* Empty */}
          {!activeJob && historyJobs.length === 0 && (
            <div className="text-center py-16 text-muted-foreground">
              <Activity className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>尚无任务记录</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
