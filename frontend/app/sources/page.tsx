"use client";

import { useEffect, useState } from "react";
import { sourcesApi, pipelineApi, Source } from "@/lib/api";
import { useJobPoller } from "@/lib/useJobPoller";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Database,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  AtSign,
  Rss,
} from "lucide-react";

function SourceTypeIcon({ type }: { type: string }) {
  return type === "twitter" ? (
    <AtSign className="h-4 w-4 text-sky-400" />
  ) : (
    <Rss className="h-4 w-4 text-green-400" />
  );
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", source_type: "twitter", handle: "", description: "" });
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

  const handleAdd = async () => {
    if (!form.name || !form.handle) {
      toast.error("名称和 handle 不能为空");
      return;
    }
    setSubmitting(true);
    try {
      await sourcesApi.create(form);
      toast.success("数据源已添加");
      setShowAdd(false);
      setForm({ name: "", source_type: "twitter", handle: "", description: "" });
      load();
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (source: Source) => {
    try {
      await sourcesApi.update(source.id, { is_enabled: !source.is_enabled });
      load();
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
      toast.success("流水线已启动");
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
            手动触发爬取
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
          {sources.map((source) => (
            <Card key={source.id} className="bg-card border-border">
              <CardContent className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <SourceTypeIcon type={source.source_type} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{source.name}</span>
                      <Badge variant="secondary" className="text-xs font-mono">
                        {source.handle}
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
                      <span>{source.doc_count} 篇文档</span>
                      {source.last_crawled_at && (
                        <span>上次爬取：{new Date(source.last_crawled_at).toLocaleString("zh-CN")}</span>
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
                      className="text-red-400 hover:text-red-300 h-7 w-7 p-0"
                      onClick={() => handleDelete(source.id, source.name)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="bg-card border-border max-w-md">
          <DialogHeader>
            <DialogTitle>添加数据源</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">类型</label>
              <Select
                value={form.source_type}
                onValueChange={(v) => setForm((f) => ({ ...f, source_type: v ?? "twitter" }))}
              >
                <SelectTrigger className="h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="twitter">Twitter / X 博主</SelectItem>
                  <SelectItem value="wechat">微信公众号</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
              <label className="text-xs text-muted-foreground mb-1 block">
                {form.source_type === "twitter" ? "Twitter Handle（@username）" : "公众号 ID / 名称"}
              </label>
              <Input
                className="h-8"
                placeholder={form.source_type === "twitter" ? "@elonmusk" : "wallstreetcn"}
                value={form.handle}
                onChange={(e) => setForm((f) => ({ ...f, handle: e.target.value }))}
              />
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
            <Button variant="outline" onClick={() => setShowAdd(false)}>取消</Button>
            <Button onClick={handleAdd} disabled={submitting}>
              {submitting && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
              添加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
