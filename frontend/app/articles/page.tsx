"use client";

import { useEffect, useState } from "react";
import { articlesApi, sourcesApi, Article, Source } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import {
  BookOpen, ExternalLink, Loader2, Rss, Search, TrendingUp, X,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function fmtDay(iso: string | null) {
  if (!iso) return "未知日期";
  const d = new Date(iso);
  const today = new Date();
  const diff = Math.floor((today.getTime() - d.getTime()) / 86400000);
  const label = diff === 0 ? "今天" : diff === 1 ? "昨天" : "";
  const base = d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  return label ? `${base}（${label}）` : base;
}

function dayKey(iso: string | null) {
  if (!iso) return "unknown";
  return iso.slice(0, 10);
}

// ── Article modal ─────────────────────────────────────────────────────────────

function ArticleModal({ article, onClose, isDaily = false }: { article: Article; onClose: () => void; isDaily?: boolean }) {
  const lines = article.content.split("\n").filter(Boolean);
  const title = isDaily ? null : (lines[0] ?? "");
  const body = isDaily ? lines : lines.slice(1);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-white text-gray-900 border-gray-200 max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader className="shrink-0">
          {title ? (
            <DialogTitle className="text-gray-900 text-base font-semibold leading-snug pr-6">{title}</DialogTitle>
          ) : (
            <VisuallyHidden><DialogTitle>文章详情</DialogTitle></VisuallyHidden>
          )}
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <Badge variant="secondary" className="text-xs">{article.source_name || article.author}</Badge>
            {article.published_at && (
              <span className="text-xs text-gray-400">{new Date(article.published_at).toLocaleString("zh-CN")}</span>
            )}
            {article.url && (
              <a href={article.url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-blue-500 hover:underline flex items-center gap-0.5">
                原文 <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </DialogHeader>
        <div className="overflow-y-auto flex-1 mt-3 pr-1">
          <div className="text-sm text-gray-700 leading-relaxed space-y-3">
            {body.length > 0 ? body.map((p, i) => <p key={i}>{p}</p>) : <p className="text-gray-400">（正文为空）</p>}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Daily card — tweet-style, no title ────────────────────────────────────────

function DailyCard({ article }: { article: Article }) {
  const text = article.content?.trim() || "（无内容）";
  return (
    <div className="flex items-start gap-3 px-4 py-4 rounded-lg border border-border bg-card">
      <Rss className="h-4 w-4 text-green-400 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {article.source_name && (
            <span className="text-xs font-medium text-foreground">{article.source_name}</span>
          )}
          {article.published_at && (
            <span className="text-xs text-muted-foreground">{fmtDate(article.published_at)}</span>
          )}
        </div>
        <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">{text}</p>
      </div>
      {article.url && (
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted-foreground/40 hover:text-primary shrink-0 mt-0.5"
          aria-label="打开原文"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}

// ── Research article card — title-based ───────────────────────────────────────

function ArticleCard({ article, onClick, showSource = true }: { article: Article; onClick: () => void; showSource?: boolean }) {
  return (
    <Card className="bg-card border-border cursor-pointer hover:border-primary/40 transition-colors"
      onClick={onClick}>
      <CardContent className="px-4 py-3">
        <div className="flex items-start gap-3">
          <Rss className="h-4 w-4 text-green-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium leading-snug line-clamp-2">{article.title || "（无标题）"}</p>
            {article.preview && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">{article.preview}</p>
            )}
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {showSource && article.source_name && (
                <Badge variant="secondary" className="text-xs px-1.5 py-0">{article.source_name}</Badge>
              )}
              {article.published_at && (
                <span className="text-xs text-muted-foreground">{fmtDate(article.published_at)}</span>
              )}
            </div>
          </div>
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0 mt-0.5" />
        </div>
      </CardContent>
    </Card>
  );
}

// ── Daily tab — grouped by date ───────────────────────────────────────────────

function DailyTab({ q }: { q: string }) {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    articlesApi.list({ content_type: "daily", q: q || undefined, limit: 500 })
      .then(setArticles)
      .finally(() => setLoading(false));
  }, [q]);

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>;
  if (articles.length === 0) return (
    <div className="text-center py-16 text-muted-foreground">
      <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-30" />
      <p>{q ? `未找到包含「${q}」的简讯` : "暂无日常简讯"}</p>
    </div>
  );

  // Group by date
  const groups = new Map<string, Article[]>();
  for (const a of articles) {
    const k = dayKey(a.published_at);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(a);
  }

  return (
    <>
      <div className="space-y-6">
        {[...groups.entries()].map(([key, items]) => (
          <div key={key}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-foreground">{fmtDay(items[0].published_at)}</span>
              <span className="text-xs text-muted-foreground">{items.length} 条</span>
            </div>
            <div className="space-y-3 pl-2 border-l-2 border-border">
              {items.map((a) => (
                <DailyCard key={a.id} article={a} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Research tab — grouped by source ─────────────────────────────────────────

function ResearchTab({ q }: { q: string }) {
  const [articles, setArticles] = useState<Article[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceFilter, setSourceFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Article | null>(null);

  useEffect(() => {
    sourcesApi.list().then((list) => setSources(list.filter((s) => s.content_type === "research")));
  }, []);

  useEffect(() => {
    setLoading(true);
    articlesApi.list({
      content_type: "research",
      source_id: sourceFilter || undefined,
      q: q || undefined,
      limit: 200,
    }).then(setArticles).finally(() => setLoading(false));
  }, [q, sourceFilter]);

  return (
    <>
      {/* Source filter pills */}
      <div className="flex items-center gap-1.5 flex-wrap mb-4">
        <button
          onClick={() => setSourceFilter("")}
          className={cn(
            "h-7 px-3 rounded-full text-xs border transition-colors",
            sourceFilter === ""
              ? "border-primary bg-primary/10 text-primary font-medium"
              : "border-border text-muted-foreground hover:text-foreground hover:border-primary/40"
          )}
        >全部</button>
        {sources.map((s) => (
          <button key={s.id} onClick={() => setSourceFilter(s.id)}
            className={cn(
              "h-7 px-3 rounded-full text-xs border transition-colors flex items-center gap-1",
              sourceFilter === s.id
                ? "border-primary bg-primary/10 text-primary font-medium"
                : "border-border text-muted-foreground hover:text-foreground hover:border-primary/40"
            )}
          >
            <Rss className="h-3 w-3" />{s.name}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : articles.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <BookOpen className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>{q ? `未找到包含「${q}」的文章` : "暂无投研文章"}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {articles.map((a) => (
            <ArticleCard key={a.id} article={a} onClick={() => setSelected(a)} showSource={!sourceFilter} />
          ))}
        </div>
      )}
      {selected && <ArticleModal article={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "daily" | "research";

export default function ArticlesPage() {
  const [tab, setTab] = useState<Tab>("daily");
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");

  const applySearch = () => setQuery(draftQuery);
  const clearSearch = () => { setDraftQuery(""); setQuery(""); };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <BookOpen className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">文章库</h1>

        {/* Tabs */}
        <div className="flex items-center gap-1 ml-2 bg-muted rounded-lg p-0.5">
          {([["daily", "日常简讯", TrendingUp], ["research", "投研知识库", BookOpen]] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              onClick={() => { setTab(id); clearSearch(); }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors",
                tab === id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="ml-auto flex items-center gap-1">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="h-8 pl-8 pr-8 w-48 text-sm"
              placeholder="搜索关键词…"
              value={draftQuery}
              onChange={(e) => setDraftQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
            />
            {draftQuery && (
              <button className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={clearSearch}>
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <Button size="sm" variant="outline" className="h-8" onClick={applySearch}>搜索</Button>
        </div>
      </div>

      {tab === "daily"    && <DailyTab    q={query} />}
      {tab === "research" && <ResearchTab q={query} />}
    </div>
  );
}
