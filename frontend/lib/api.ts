const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  name: string;
  source_type: "twitter" | "wechat";
  handle: string;
  description: string;
  is_enabled: boolean;
  status: "ok" | "error";
  last_crawled_at: string | null;
  created_at: string;
  doc_count: number;
}

export interface Report {
  id: string;
  report_date: string;
  report_type: "pre" | "post";
  sentiment: SentimentData;
  hotspots: HotspotData;
  stock_prices: Record<string, StockPrice>;
  summary_text: string;
  article_count: number;
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

export interface Prompt {
  id: string;
  agent_name: string;
  prompt_text: string;
  version: number;
  is_active: boolean;
  updated_at: string;
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── Sources API ────────────────────────────────────────────────────────────

export const sourcesApi = {
  list: () => request<Source[]>("/api/sources"),
  get: (id: string) => request<Source>(`/api/sources/${id}`),
  create: (data: { name: string; source_type: string; handle: string; description?: string }) =>
    request<Source>("/api/sources", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Source>) =>
    request<Source>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetch(`${BASE}/api/sources/${id}`, { method: "DELETE" }),
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
  trigger: (report_type: string = "manual") =>
    request<{ job_id: string; message: string }>("/api/pipeline/trigger", {
      method: "POST",
      body: JSON.stringify({ report_type }),
    }),
  jobStatus: (job_id: string) =>
    request<JobStatus>(`/api/pipeline/jobs/${job_id}`),
  listJobs: (limit?: number) =>
    request<JobStatus[]>(`/api/pipeline/jobs?limit=${limit ?? 20}`),
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

// ── Chat SSE ──────────────────────────────────────────────────────────────

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

  fetch(`${BASE}/api/chat/stream`, {
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
