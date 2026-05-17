"use client";

import { useEffect, useState } from "react";
import { sourcesApi, pipelineApi, Source } from "@/lib/api";
import { useJobPoller } from "@/lib/useJobPoller";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  BookOpen,
  Database,
  Loader2,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  Rss,
  TrendingUp,
} from "lucide-react";

const CONTENT_TYPE_CONFIG = {
  daily: {
    label: "日常简讯",
    icon: TrendingUp,
    className: "border-blue-500/40 text-blue-400",
    description: "短线交易、市场动态 — 直接存库，参与每日报告",
  },
  research: {
    label: "投研知识库",
    icon: BookOpen,
    className: "border-amber-500/40 text-amber-400",
    description: "行业研究、深度分析 — 进入 RAG 向量知识库",
  },
} as const;

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editSource, setEditSource] = useState<Source | null>(null);
  const [form, setForm] = useState({
    name: "",
    source_type: "rss",
    handle: "",
    description: "",
    content_type: "daily" as "daily" | "research",
  });
  const [submitting, setSubmitting] = useState(false);

  const { status: jobStatus, isPolling, startPolling } = useJobPoller();

  const load = async () => {
    setLoading(true);
    try {
      setSources(await sourcesApi.list());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const resetForm = () =>
    setForm({ name: "", source_type: "rss", handle: "", description: "", content_type: "daily" });

  const handleAdd = async () => {
    if (!form.name || !form.handle) {
      toast.error("名称和 Feed URL 不能为空");
      return;
    }
    setSubmitting(true);
    try {
      const created = await sourcesApi.create(form);
      toast.success("数据源已添加，正在首次抓取…");
      setShowAdd(false);
      resetForm();
      load();
      const { job_id } = await pipelineApi.crawlSource(created.id);
      startPolling(job_id);
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const openEdit = (source: Source) => {
    setEditSource(source);
    setForm({
      name: source.name,
      source_type: source.source_type,
      handle: source.handle,
      description: source.description,
      content_type: source.content_type,
    });
  };

  const handleEdit = async () => {
    if (!editSource || !form.name || !form.handle) {
      toast.error("名称和 URL 不能为空");
      return;
    }
    setSubmitting(true);
    try {
      await sourcesApi.update(editSource.id, {
        name: form.name,
        handle: form.handle,
        description: form.description,
        content_type: form.content_type,
      });
      toast.success("已保存");
      setEditSource(null);
      load();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (source: Source) => {
    const enabling = !source.is_enabled;
    try {
      await sourcesApi.update(source.id, { is_enabled: enabling });
      load();
      if (enabling) {
        const { job_id } = await pipelineApi.crawlSource(source.id);
        startPolling(job_id);
        toast.success(`${source.name} 已启用，正在抓取最新内容…`);
      }
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确认删除数据源「${name}」？此操作不可逆。`)) return;
    try {
      await sourcesApi.delete(id);
      toast.success("已删除");
      load();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  const handleTrigger = async () => {
    try {
      const { job_id } = await pipelineApi.trigger("manual");
      startPolling(job_id);
      toast.success("全源数据同步已启动");
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Database className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">数据源配置</h1>
        <div className="ml-auto flex items-center gap-2">
          <JobStatusBadge status={jobStatus} isPolling={isPolling} />
          <Button size="sm" variant="outline" onClick={handleTrigger} disabled={isPolling}>
            {isPolling ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Play className="h-3 w-3 mr-1" />}
            全源同步
          </Button>
          <Button size="sm" variant="outline" onClick={load}>
            <RefreshCw className="h-3 w-3 mr-1" />
            刷新
          </Button>
          <Button size="sm" onClick={() => setShowAdd(true)}>
            <Plus className="h-3 w-3 mr-1" />
            添加数据源
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Database className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>尚未添加任何数据源</p>
          <Button className="mt-4" onClick={() => setShowAdd(true)}>
            <Plus className="h-3 w-3 mr-1" /> 添加第一个数据源
          </Button>
        </div>
      ) : (
        <div className="grid gap-3">
          {sources.map((source) => {
            const ct = CONTENT_TYPE_CONFIG[source.content_type] ?? CONTENT_TYPE_CONFIG.daily;
            const CtIcon = ct.icon;
            return (
              <Card key={source.id} className="bg-card border-border">
                <CardContent className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Rss className="h-4 w-4 text-green-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm">{source.name}</span>
                        <Badge
                          variant="outline"
                          className={`text-xs ${ct.className} gap-1`}
                        >
                          <CtIcon className="h-3 w-3" />
                          {ct.label}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={
                            source.status === "error"
                              ? "border-red-500/40 text-red-400 text-xs"
                              : "border-green-500/40 text-green-400 text-xs"
                          }
                        >
                          {source.status === "error" ? "异常" : "正常"}
                        </Badge>
                      </div>
                      <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                        {source.last_crawled_at && (
                          <span className="shrink-0">
                            上次同步：{new Date(source.last_crawled_at).toLocaleString("zh-CN")}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant={source.is_enabled ? "outline" : "secondary"}
                        onClick={() => handleToggle(source)}
                        className="text-xs h-7"
                      >
                        {source.is_enabled ? "启用中" : "已停用"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                        onClick={() => openEdit(source)}
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-400 hover:text-red-300 h-7 w-7 p-0"
                        onClick={() => handleDelete(source.id, source.name)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add dialog */}
      <SourceFormDialog
        open={showAdd}
        onOpenChange={(o) => { if (!o) { setShowAdd(false); resetForm(); } else setShowAdd(true); }}
        title="添加数据源"
        form={form}
        setForm={setForm}
        onSubmit={handleAdd}
        submitting={submitting}
      />

      {/* Edit dialog */}
      <SourceFormDialog
        open={!!editSource}
        onOpenChange={(o) => { if (!o) setEditSource(null); }}
        title="编辑数据源"
        form={form}
        setForm={setForm}
        onSubmit={handleEdit}
        submitting={submitting}
      />
    </div>
  );
}

interface FormState {
  name: string;
  source_type: string;
  handle: string;
  description: string;
  content_type: "daily" | "research";
}

function SourceFormDialog({
  open,
  onOpenChange,
  title,
  form,
  setForm,
  onSubmit,
  submitting,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  onSubmit: () => void;
  submitting: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white text-gray-900 border-gray-200 max-w-md [&_label]:text-gray-500 [&_input]:bg-white [&_input]:border-gray-200 [&_input]:text-gray-900 [&_input::placeholder]:text-gray-400">
        <DialogHeader>
          <DialogTitle className="text-gray-900">{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">显示名称</label>
            <Input
              className="h-8"
              placeholder="e.g. 华尔街见闻"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">RSS Feed URL</label>
            <Input
              className="h-8 font-mono text-xs"
              placeholder="https://example.com/feed.xml"
              value={form.handle}
              onChange={(e) => setForm((f) => ({ ...f, handle: e.target.value }))}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">用途分类</label>
            <div className="grid grid-cols-2 gap-2">
              {(["daily", "research"] as const).map((ct) => {
                const cfg = CONTENT_TYPE_CONFIG[ct];
                const Icon = cfg.icon;
                const selected = form.content_type === ct;
                return (
                  <button
                    key={ct}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, content_type: ct }))}
                    className={`flex flex-col gap-1 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                      selected
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 font-medium">
                      <Icon className="h-3.5 w-3.5" />
                      {cfg.label}
                    </div>
                    <span className="text-[11px] leading-tight text-gray-400">{cfg.description}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">描述（可选）</label>
            <Input
              className="h-8"
              placeholder="简短描述"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            className="border-gray-200 text-gray-700 hover:bg-gray-50"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button onClick={onSubmit} disabled={submitting}>
            {submitting && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
            {title.startsWith("添加") ? "添加" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
