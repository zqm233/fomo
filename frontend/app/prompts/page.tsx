"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { promptsApi, Prompt } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Brain,
  Flame,
  FileText,
  History,
  Loader2,
  MessageSquare,
  RotateCcw,
  Save,
  Sparkles,
  Undo2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type AgentId = "sentiment_agent" | "hotspot_agent" | "summary_agent" | "chat_agent";

const AGENTS: {
  id: AgentId;
  label: string;
  description: string;
  icon: LucideIcon;
  accent: string;
}[] = [
  {
    id: "sentiment_agent",
    label: "情绪分析",
    description: "RSS / 社媒文本 → 多空情绪 JSON",
    icon: Brain,
    accent: "border-violet-500/40 bg-violet-500/10 text-violet-400",
  },
  {
    id: "hotspot_agent",
    label: "热点提取",
    description: "归纳当日市场热点与主题",
    icon: Flame,
    accent: "border-orange-500/40 bg-orange-500/10 text-orange-400",
  },
  {
    id: "summary_agent",
    label: "盘前/盘后总结",
    description: "生成简报式盘前盘后摘要",
    icon: FileText,
    accent: "border-sky-500/40 bg-sky-500/10 text-sky-400",
  },
  {
    id: "chat_agent",
    label: "RAG 问答",
    description: "基于知识库的对话与引用",
    icon: MessageSquare,
    accent: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  },
];

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function PromptEditor({
  agentId,
  config,
  onDirtyChange,
}: {
  agentId: AgentId;
  config: (typeof AGENTS)[number];
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [editText, setEditText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<Prompt[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<Prompt | null>(null);
  const [rollingBack, setRollingBack] = useState(false);

  const dirty = prompt !== null && editText !== prompt.prompt_text;
  const Icon = config.icon;
  const onDirtyChangeRef = useRef(onDirtyChange);
  onDirtyChangeRef.current = onDirtyChange;

  useEffect(() => {
    onDirtyChangeRef.current?.(dirty);
  }, [dirty]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPrompt(null);
    setEditText("");
    promptsApi
      .get(agentId)
      .then((p) => {
        if (!cancelled) {
          setPrompt(p);
          setEditText(p.prompt_text);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) toast.error((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  const handleSave = useCallback(async () => {
    if (!editText.trim()) {
      toast.error("Prompt 不能为空");
      return;
    }
    setSaving(true);
    try {
      const updated = await promptsApi.update(agentId, editText);
      setPrompt(updated);
      toast.success(`已保存为 v${updated.version}`);
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [agentId, editText]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (dirty && !saving) void handleSave();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, saving, handleSave]);

  const openHistory = async () => {
    setHistoryOpen(true);
    setHistoryLoading(true);
    setPreviewVersion(null);
    try {
      const h = await promptsApi.history(agentId);
      setHistory(h);
      const current = h.find((x) => x.is_active) ?? h[0];
      setPreviewVersion(current ?? null);
    } catch (e: unknown) {
      toast.error((e as Error).message);
      setHistoryOpen(false);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleRollback = async (version: number) => {
    setRollingBack(true);
    try {
      const rolled = await promptsApi.rollback(agentId, version);
      setPrompt(rolled);
      setEditText(rolled.prompt_text);
      setHistoryOpen(false);
      toast.success(`已回滚到 v${version}`);
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setRollingBack(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-1 flex-col gap-4 p-6">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-muted" />
        <div className="min-h-[360px] flex-1 animate-pulse rounded-xl bg-muted/60" />
      </div>
    );
  }

  if (!prompt) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
        无法加载 Prompt，请检查后端连接
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-5 py-4">
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border",
              config.accent
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold leading-tight">{config.label}</h2>
            <p className="text-xs text-muted-foreground">{config.description}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <Badge variant="outline" className="font-mono text-xs">
              v{prompt.version}
            </Badge>
            {dirty && (
              <Badge variant="secondary" className="text-xs text-amber-600 dark:text-amber-400">
                未保存
              </Badge>
            )}
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {formatDateTime(prompt.updated_at)}
            </span>
          </div>
        </div>

        {/* Editor */}
        <div className="flex min-h-0 flex-1 flex-col gap-3 p-5">
          <Textarea
            className="min-h-[min(520px,calc(100vh-16rem))] flex-1 resize-y rounded-xl border-border/80 bg-muted/30 font-mono text-sm leading-relaxed shadow-inner focus-visible:ring-primary/30"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            placeholder="在此编辑 System Prompt…"
            spellCheck={false}
          />
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>{editText.length.toLocaleString()} 字符</span>
            <span className="hidden sm:inline">·</span>
            <span className="hidden sm:inline">
              {editText.split(/\n/).length} 行
            </span>
            <span className="ml-auto hidden text-muted-foreground/80 sm:inline">
              ⌘S / Ctrl+S 保存
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2 border-t border-border bg-muted/20 px-5 py-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => openHistory()}
          >
            <History className="mr-1.5 h-3.5 w-3.5" />
            历史版本
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={!dirty}
            onClick={() => setEditText(prompt.prompt_text)}
          >
            <Undo2 className="mr-1.5 h-3.5 w-3.5" />
            撤销修改
          </Button>
          <Button
            type="button"
            size="sm"
            className="ml-auto"
            onClick={() => void handleSave()}
            disabled={saving || !dirty || !editText.trim()}
          >
            {saving ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-3.5 w-3.5" />
            )}
            保存新版本
          </Button>
        </div>
      </div>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-2xl" showCloseButton>
          <DialogHeader>
            <DialogTitle>历史版本 — {config.label}</DialogTitle>
            <DialogDescription>
              左侧选择版本预览，确认后回滚；回滚会生成新的活跃版本。
            </DialogDescription>
          </DialogHeader>

          {historyLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid min-h-0 flex-1 gap-4 sm:grid-cols-[220px_1fr]">
              <ScrollArea className="h-[min(50vh,320px)] rounded-lg border border-border">
                <div className="space-y-1 p-2">
                  {history.map((h) => (
                    <button
                      key={h.id}
                      type="button"
                      onClick={() => setPreviewVersion(h)}
                      className={cn(
                        "flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        previewVersion?.id === h.id
                          ? "bg-primary/15 text-foreground"
                          : "hover:bg-muted"
                      )}
                    >
                      <span className="flex w-full items-center gap-2">
                        <span className="font-mono font-medium">v{h.version}</span>
                        {h.is_active && (
                          <Badge className="h-5 px-1.5 text-[10px]">当前</Badge>
                        )}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(h.updated_at)}
                      </span>
                    </button>
                  ))}
                </div>
              </ScrollArea>

              <ScrollArea className="h-[min(50vh,320px)] rounded-lg border border-border bg-muted/20 p-3">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/90">
                  {previewVersion?.prompt_text ?? "选择左侧版本查看内容"}
                </pre>
              </ScrollArea>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setHistoryOpen(false)}>
              关闭
            </Button>
            <Button
              type="button"
              disabled={
                rollingBack ||
                historyLoading ||
                !previewVersion ||
                previewVersion.is_active
              }
              onClick={() => previewVersion && void handleRollback(previewVersion.version)}
            >
              {rollingBack ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
              )}
              回滚到 v{previewVersion?.version ?? "—"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function PromptsPage() {
  const [selected, setSelected] = useState<AgentId>(AGENTS[0].id);
  const [isDirty, setIsDirty] = useState(false);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setIsDirty((prev) => (prev === dirty ? prev : dirty));
  }, []);

  const trySelect = (id: AgentId) => {
    if (id === selected) return;
    if (isDirty) {
      if (!window.confirm("当前 Agent 有未保存的修改，确定切换？")) return;
    }
    setIsDirty(false);
    setSelected(id);
  };

  const active = AGENTS.find((a) => a.id === selected)!;

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold tracking-tight">Prompt 管理</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          编辑各 Agent 的 System Prompt，保存后立即生效，无需重启服务。
        </p>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch">
        {/* Agent nav */}
        <nav className="flex shrink-0 flex-row gap-2 overflow-x-auto pb-1 lg:w-52 lg:flex-col lg:overflow-visible lg:pb-0">
          {AGENTS.map((agent) => {
            const Icon = agent.icon;
            const isActive = selected === agent.id;
            return (
              <button
                key={agent.id}
                type="button"
                onClick={() => trySelect(agent.id)}
                className={cn(
                  "flex min-w-[140px] flex-1 flex-col items-start gap-2 rounded-xl border px-3 py-3 text-left transition-all lg:min-w-0 lg:flex-none",
                  isActive
                    ? "border-primary/50 bg-primary/10 shadow-sm ring-1 ring-primary/20"
                    : "border-border bg-card/50 hover:border-primary/30 hover:bg-muted/50"
                )}
              >
                <span className="flex w-full items-center gap-2">
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
                      agent.accent
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-medium leading-tight">{agent.label}</span>
                  {isActive && isDirty && (
                    <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-amber-500" title="未保存" />
                  )}
                </span>
                <span className="line-clamp-2 text-xs text-muted-foreground">
                  {agent.description}
                </span>
              </button>
            );
          })}
        </nav>

        <Separator className="lg:hidden" />

        {/* Editor panel */}
        <section className="flex min-h-[min(640px,calc(100vh-10rem))] min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <PromptEditor
            key={selected}
            agentId={selected}
            config={active}
            onDirtyChange={handleDirtyChange}
          />
        </section>
      </div>
    </div>
  );
}
