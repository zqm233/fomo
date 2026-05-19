export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
    });
  } catch (e) {
    const isNetwork =
      e instanceof TypeError &&
      (e.message === "Failed to fetch" || e.message.includes("fetch"));
    const hint =
      "请在本机另开终端运行后端: make dev-backend（默认 http://localhost:8000）。";
    throw new Error(
      isNetwork
        ? `无法连接 API ${url}（后端未启动或地址错误）。${hint}`
        : `请求失败 ${url}: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Article {
  id: string;
  source_id: string;
  source_name: string;
  content_type: "daily" | "research";
  author: string;
  title: string;
  preview: string;
  content: string;
  url: string;
  published_at: string | null;
  created_at: string;
  vectorized: boolean;
}

export interface ClientMeta {
  rsshub_twitter_base: string;
}

export interface Source {
  id: string;
  name: string;
  source_type: string;
  handle: string;
  description: string;
  content_type: "daily" | "research";
  is_enabled: boolean;
  status: "ok" | "error";
  last_crawled_at: string | null;
  created_at: string;
  doc_count: number;
}

/** 简报中按博主汇总的简讯条数与预览（pipeline 写入） */
export interface SourceDigestRow {
  source_name: string;
  item_count: number;
  preview: string;
}

/** 热门股池条目（与 /api/tickers/hot 一致） */
export interface TickerArticleSnippet {
  article_id: string;
  source_name: string;
  preview: string;
  url: string;
  mention_date: string;
}

export interface HotTicker {
  ticker: string;
  /** 近 N 个美股交易日窗口内「博主×交易日×标的」去重积分 */
  mention_count: number;
  sources: string[];
  articles: TickerArticleSnippet[];
  price: number | null;
  change_pct: number | null;
  sparkline: number[];
  name: string;
}

export interface Report {
  id: string;
  report_date: string;
  report_type: "pre" | "post";
  sentiment: SentimentData;
  hotspots: HotspotData;
  stock_prices: Record<string, StockPrice>;
  summary_text: string;
  /** 本次生成该份简报时，时间窗内纳入分析的简讯条数（不是「简报篇数」） */
  article_count: number;
  /** 按博主：今日窗口内简讯条数 + 首条预览；旧数据可能为空数组 */
  source_digest: SourceDigestRow[];
  /** 盘前/盘后简报保存瞬间的热门股池快照（与「热门股」页同算法）；旧简报可能为空 */
  hot_pool?: HotTicker[];
  created_at: string;
}

export interface SentimentData {
  overall_score: number;
  label: string;
  bull_ratio: number;
  bear_ratio: number;
  key_reasons: string[];
  source_sentiments: Array<{ source: string; score: number; summary: string }>;
}

export interface HotspotData {
  keywords: string[];
  themes: Array<{ name: string; description: string; mentions: number }>;
  hot_tickers: Array<{ ticker: string; context: string }>;
  events: Array<{ title: string; summary: string }>;
}

export interface StockPrice {
  symbol: string;
  price: number;
  change_pct: number;
  volume: number;
  name: string;
}

export interface JobStatus {
  job_id: string;
  run_type: string;
  status: "queued" | "running" | "success" | "failed";
  started_at: string | null;
  finished_at: string | null;
  error_msg: string;
  articles_crawled: number;
  created_at: string;
}

export interface TaskStep {
  key: string;
  name: string;
  status: "pending" | "running" | "success" | "failed";
  detail: string;
}

export interface SourceTask {
  id: string;
  source_id: string;
  source_name: string;
  source_type: string;
  status: "pending" | "running" | "success" | "failed";
  articles_found: number;
  error_msg: string;
  steps: TaskStep[];
  started_at: string | null;
  finished_at: string | null;
}

export interface Prompt {
  id: string;
  agent_name: string;
  prompt_text: string;
  version: number;
  is_active: boolean;
  updated_at: string;
  created_at: string;
}

// ── Public meta (SPA hints, no secrets) ───────────────────────────────────

export const metaApi = {
  clientConfig: () => request<ClientMeta>("/api/meta/client-config"),
};

// ── Sources API ────────────────────────────────────────────────────────────

export const sourcesApi = {
  list: () => request<Source[]>("/api/sources"),
  get: (id: string) => request<Source>(`/api/sources/${id}`),
  create: (data: {
    name: string;
    source_type: string;
    feed_kind?: "custom" | "rsshub_twitter";
    handle?: string;
    twitter_username?: string;
    description?: string;
    content_type?: string;
  }) => request<Source>("/api/sources", { method: "POST", body: JSON.stringify(data) }),
  update: (
    id: string,
    data: Partial<Source> & {
      feed_kind?: "custom" | "rsshub_twitter";
      twitter_username?: string;
    }
  ) => request<Source>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetch(`${API_BASE}/api/sources/${id}`, { method: "DELETE" }),
};

// ── Articles API ──────────────────────────────────────────────────────────

export const articlesApi = {
  list: (params?: { source_id?: string; content_type?: string; q?: string; limit?: number; offset?: number }) => {
    const p = new URLSearchParams();
    if (params?.source_id)    p.set("source_id", params.source_id);
    if (params?.content_type) p.set("content_type", params.content_type);
    if (params?.q)            p.set("q", params.q);
    if (params?.limit)        p.set("limit", String(params.limit));
    if (params?.offset)       p.set("offset", String(params.offset));
    return request<Article[]>(`/api/articles?${p}`);
  },
  count: (params?: { source_id?: string; content_type?: string; q?: string }) => {
    const p = new URLSearchParams();
    if (params?.source_id)    p.set("source_id", params.source_id);
    if (params?.content_type) p.set("content_type", params.content_type);
    if (params?.q)            p.set("q", params.q);
    return request<{ count: number }>(`/api/articles/count?${p}`);
  },
  get: (id: string) => request<Article>(`/api/articles/${id}`),
};

// ── Reports API ───────────────────────────────────────────────────────────

export const reportsApi = {
  list: (params?: { report_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.report_type) q.set("report_type", params.report_type);
    if (params?.limit) q.set("limit", String(params.limit));
    return request<Report[]>(`/api/reports?${q}`);
  },
  latest: (report_type: "pre" | "post") =>
    request<Report>(`/api/reports/latest?report_type=${report_type}`),
  get: (id: string) => request<Report>(`/api/reports/${id}`),
  byDate: (date: string) => request<Report[]>(`/api/reports/by-date/${date}`),
};

// ── Pipeline API ──────────────────────────────────────────────────────────

export const pipelineApi = {
  trigger: (report_type: string = "manual", opts?: { skip_crawl?: boolean }) =>
    request<{ job_id: string; message: string }>("/api/pipeline/trigger", {
      method: "POST",
      body: JSON.stringify({
        report_type,
        skip_crawl: Boolean(opts?.skip_crawl),
      }),
    }),
  jobStatus: (job_id: string) =>
    request<JobStatus>(`/api/pipeline/jobs/${job_id}`),
  listJobs: (limit?: number) =>
    request<JobStatus[]>(`/api/pipeline/jobs?limit=${limit ?? 20}`),
  jobTasks: (job_id: string) =>
    request<SourceTask[]>(`/api/pipeline/jobs/${job_id}/tasks`),
  cancelJob: (job_id: string) =>
    request<{ message: string }>(`/api/pipeline/jobs/${job_id}/cancel`, { method: "POST" }),
  retryTask: (task_id: string) =>
    request<{ job_id: string; message: string }>(`/api/pipeline/tasks/${task_id}/retry`, { method: "POST" }),
  deleteTask: (task_id: string) =>
    fetch(`${API_BASE}/api/pipeline/tasks/${task_id}`, { method: "DELETE" }),
  crawlSource: (source_id: string) =>
    request<{ job_id: string; message: string }>(`/api/pipeline/sources/${source_id}/crawl`, { method: "POST" }),
  schedulerStatus: () => request<Array<{ id: string; name: string; next_run: string | null }>>("/api/pipeline/scheduler"),
};

// ── Prompts API ───────────────────────────────────────────────────────────

export const promptsApi = {
  list: () => request<Prompt[]>("/api/prompts"),
  get: (agent_name: string) => request<Prompt>(`/api/prompts/${agent_name}`),
  update: (agent_name: string, prompt_text: string) =>
    request<Prompt>(`/api/prompts/${agent_name}`, {
      method: "PUT",
      body: JSON.stringify({ prompt_text }),
    }),
  history: (agent_name: string) =>
    request<Prompt[]>(`/api/prompts/${agent_name}/history`),
  rollback: (agent_name: string, version: number) =>
    request<Prompt>(`/api/prompts/${agent_name}/rollback/${version}`, { method: "POST" }),
};

// ── Chat REST ─────────────────────────────────────────────────────────────

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
  last_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export const chatApi = {
  listSessions: () => request<ChatSession[]>("/api/chat/sessions"),
  getHistory: (sessionId: string) => request<ChatMessage[]>(`/api/chat/history/${sessionId}`),
  deleteSession: (sessionId: string) =>
    request<void>(`/api/chat/history/${sessionId}`, { method: "DELETE" }),
};

// ── Chat SSE ──────────────────────────────────────────────────────────────

export const tickersApi = {
  hot: () => request<HotTicker[]>(`/api/tickers/hot`),
};

export function streamChat(
  question: string,
  sessionId: string | null,
  sourceIds: string[],
  onToken: (token: string) => void,
  onSessionId: (id: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController();

  fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      source_ids: sourceIds,
    }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`Chat API ${res.status}`);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            if (msg.type === "token") onToken(msg.content);
            else if (msg.type === "session_id") onSessionId(msg.session_id);
            else if (msg.type === "done") onDone();
          } catch {
            /* ignore malformed */
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") onError(err);
    });

  return controller;
}
