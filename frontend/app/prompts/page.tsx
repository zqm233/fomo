"use client";

import { useEffect, useState } from "react";
import { promptsApi, Prompt } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Loader2, Save, Settings, RotateCcw } from "lucide-react";

const AGENT_LABELS: Record<string, string> = {
  sentiment_agent: "情绪分析 Agent",
  hotspot_agent: "热点提取 Agent",
  summary_agent: "盘前/盘后总结 Agent",
  chat_agent: "RAG 问答 Agent",
};

function PromptEditor({ agentName }: { agentName: string }) {
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState<Prompt[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    promptsApi.get(agentName).then((p) => {
      setPrompt(p);
      setEditText(p.prompt_text);
    });
  }, [agentName]);

  const handleSave = async () => {
    if (!editText.trim()) return;
    setSaving(true);
    try {
      const updated = await promptsApi.update(agentName, editText);
      setPrompt(updated);
      toast.success(`${AGENT_LABELS[agentName]} Prompt 已保存（v${updated.version}）`);
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleHistory = async () => {
    const h = await promptsApi.history(agentName);
    setHistory(h);
    setShowHistory(true);
  };

  const handleRollback = async (version: number) => {
    try {
      const rolled = await promptsApi.rollback(agentName, version);
      setPrompt(rolled);
      setEditText(rolled.prompt_text);
      setShowHistory(false);
      toast.success(`已回滚到 v${version}`);
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  };

  if (!prompt) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs">v{prompt.version}</Badge>
        <span className="text-xs text-muted-foreground">
          更新于 {new Date(prompt.updated_at).toLocaleString("zh-CN")}
        </span>
        <Button size="sm" variant="ghost" className="ml-auto text-xs" onClick={handleHistory}>
          <RotateCcw className="h-3 w-3 mr-1" />
          历史版本
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving || editText === prompt.prompt_text}>
          {saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
          保存新版本
        </Button>
      </div>

      <Textarea
        className="min-h-[280px] font-mono text-sm bg-background resize-none"
        value={editText}
        onChange={(e) => setEditText(e.target.value)}
        placeholder="在此编辑 Prompt…"
      />

      {showHistory && (
        <Card className="border-border bg-card">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm">历史版本（点击回滚）</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 space-y-2">
            {history.map((h) => (
              <div
                key={h.id}
                className="flex items-center gap-2 p-2 rounded border border-border hover:border-primary/30 cursor-pointer"
                onClick={() => handleRollback(h.version)}
              >
                <Badge variant={h.is_active ? "default" : "outline"} className="text-xs shrink-0">
                  v{h.version}
                </Badge>
                <span className="text-xs text-muted-foreground flex-1 truncate">
                  {h.prompt_text.slice(0, 80)}…
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {new Date(h.updated_at).toLocaleDateString("zh-CN")}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function PromptsPage() {
  const agentNames = Object.keys(AGENT_LABELS);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Settings className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">Prompt 管理</h1>
        <span className="text-xs text-muted-foreground ml-2">
          修改后立即生效，无需重启服务
        </span>
      </div>

      <Tabs defaultValue={agentNames[0]}>
        <TabsList className="bg-muted">
          {agentNames.map((name) => (
            <TabsTrigger key={name} value={name} className="text-xs">
              {AGENT_LABELS[name]}
            </TabsTrigger>
          ))}
        </TabsList>
        {agentNames.map((name) => (
          <TabsContent key={name} value={name} className="mt-4">
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <PromptEditor agentName={name} />
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
