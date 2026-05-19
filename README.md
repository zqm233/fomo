# FOMO — 美股财经投研 AI Agent 系统

> 个人投研 + AI Agent 求职作品集项目

### FOMO（美股财经投研 AI 全栈，LangChain 多 Agent + RAG），[https://github.com/zqm233/fomo](https://github.com/zqm233/fomo)

#### 项目描述

面向美股资讯与投研自动化的个人全栈作品：以 **RSS 财经源** 为入口，经解析去重与 **Chroma 向量库** 沉淀知识，配合 **LangChain 多 Agent** 做情绪 / 热点 / 总结分析并生成每日简报；前端用 **Next.js** 聚合数据源、简报、文章库、流水线任务与 **SSE 流式 RAG 对话**，后端 **FastAPI + APScheduler** 负责定时流水线与行情联动展示。

#### 工作内容：

- **每日流水线编排**：RSS 爬取 → 解析去重 → 向量化入库 → 情绪 / 热点 / 总结 Agent 顺序产出报告；集成热门标的池、文章留存清理与美股市历/行情快照（指数与个股联动简报）。
- **RAG 与工具层**：按数据源划分 Chroma Collection，检索 Tool + DB 读写；聊天接口 **SSE** 流式返回。
- **数据与部署**：**SQLAlchemy + Alembic** 管理 schema；SQLite 持久化；**uv** 锁依赖、**Makefile** 本地/Docker 一键流程。

#### 技术栈

Python / FastAPI / Next.js / TypeScript / LangChain / Chroma / SQLAlchemy / Alembic / APScheduler / Tailwind CSS / uv

---

## 功能亮点

| 功能 | 说明 |
|------|------|
| 自动爬取 | RSS 源定时拉取，流水线内解析去重 |
| 向量知识库 | Chroma，每数据源独立 Collection，语义去重 |
| 情绪分析 | 市场多空情绪打分，博主横向对比 |
| 热点提取 | 关键词 / 主题 / 热门标的 / 重要事件 |
| 股价联动 | yfinance 实时拉取 SPY/QQQ 及被提及个股涨跌 |
| 盘前/盘后简报 | 美东 08:30 / 16:30 全自动生成，推送通知 |
| RAG 对话 | 前端聊天窗口，SSE 流式输出，支持多博主检索 |
| Prompt 管理 | 前端可视化编辑各 Agent Prompt，版本回滚 |
| Job 状态轮询 | 手动触发流水线后实时查看进度 |
| Docker 部署 | `docker compose up` 一键启动 |

---

## 技术栈

- **前端**：Next.js 14 (App Router) · TypeScript · shadcn/ui · Tailwind CSS · Recharts
- **后端**：Python 3.12+ · FastAPI · LangChain · APScheduler · **依赖用 [uv](https://docs.astral.sh/uv/) 管理**
- **AI**：OpenAI GPT-4o-mini（可替换任意 OpenAI 兼容模型）
- **向量库**：Chroma (持久化)
- **数据库**：SQLite (SQLAlchemy ORM)
- **爬虫**：x-tweet-fetcher · requests + BeautifulSoup
- **股价**：yfinance
- **通知**：Telegram Bot / 企业微信 Webhook

---

## 快速开始（本地开发）

### 1. 克隆项目

```bash
git clone <your-repo-url> fomo
cd fomo
```

### 2. 配置后端环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 OPENAI_API_KEY 等配置
```

### 3. 安装依赖（一次性）

需要 **Python 3.12+** 与 **[uv](https://docs.astral.sh/uv/)**（`brew install uv` 或官方安装脚本）。在仓库根目录：

```bash
make install
```

会：占位复制 `backend/.env`、`frontend/.env.local`（若不存在）、创建 `data/`、克隆 x-tweet-fetcher、`uv sync`、前端 `npm install`。

### 4. 启动开发服务

需**两个终端**：

```bash
make dev-backend    # 终端 1：http://127.0.0.1:8000/docs
make dev-frontend   # 终端 2：http://localhost:3000
```

**更新后端依赖时**：在 `backend/pyproject.toml` 中改版本后执行 `cd backend && uv lock`（Docker 构建与本地均用 `uv.lock`）。

---

## Docker 一键部署

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env

# 2. 创建数据目录
mkdir -p data

# 3. 启动（前台可改 `docker compose up --build -d`）
make up
# 或: docker compose up --build -d

# 停止
make down
```

服务地址：
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 部署后端到 Render

仓库根目录已提供 [`render.yaml`](render.yaml)（Docker 蓝图）。要点：

1. **在 Render**：New → **Blueprint**，连接本仓库并按提示创建 Web Service（或导入 `render.yaml`）。
2. **构建上下文**：镜像使用 `backend/Dockerfile`，`dockerContext` 为 **`backend`**，与现有 Docker 构建一致。
3. **端口**：平台会注入 **`PORT`**；镜像默认 `CMD` 使用 `${PORT:-8000}`；蓝图中 **`dockerCommand`** 在启动前执行 **`alembic upgrade head`** 再拉起 `uvicorn`。
4. **环境变量（在 Dashboard 里填密钥类）**

   | 变量 | 说明 |
   |------|------|
   | `DATABASE_URL` | 推荐整串 Postgres URL（如 Supabase）；需含 `sslmode=require` |
   | `OPENAI_API_KEY` | LLM + 向量（方舟下 `EMBEDDING_PROVIDER=ark`）；也可单独设 `ARK_API_KEY` |
   | `CORS_ORIGINS` | 前端生产地址，逗号分隔，例如 `https://你的域名` |
   | `EMBEDDING_PROVIDER` | 云上默认 **`ark`**（豆包多模态 embedding：`volcenginesdkarkruntime`）；本机 **`local`**=BGE；**`openai`**=兼容 `/embeddings` |
   | `OPENAI_BASE_URL` | 方舟 **对话** LangChain/OpenAI 的根 URL；向量在 `ark` 模式下由 **Ark SDK 默认网关** 请求（一般不必再配置 Embedding URL，除非用 `ARK_API_BASE_URL` 覆盖）。 |

   其余见 `backend/.env.example`（定时任务、`LLM_MODEL`、通知等按需配置）。

5. **健康检查**：路径 **`/api/health`**。
6. **区域与档位**：按需编辑 `render.yaml` 里的 `region`、`plan`（如改为 `singapore`、`free` 等）。

前端若部署在 **Vercel / 别处**，把该平台上的 `NEXT_PUBLIC_API_URL` 指到 Render 给出的 `https://<service>.onrender.com`。

### 模式二：流水线打镜像 → GHCR → Render 拉取（与 Blueprint 二选一）

与「Blueprint 直接在 Render 从你仓库里的 Dockerfile 构建」不同，另一种是 **先在 GitHub Actions 构建并推到 GHCR**，Render 只做 **运行时拉镜像**。

1. **确保 `main` 推送能跑绿** [`.github/workflows/docker-build-deploy.yml`](.github/workflows/docker-build-deploy.yml)：未配置 `NEXT_PUBLIC_API_URL` 时只会构建并推送 **`backend`** 镜像（`ghcr.io/<小写仓库名>/backend:latest` 与 `:sha`），不会构建前端镜像。
2. **把 GHCR 包设为公开**，或在 Render **Environment** 中为 `ghcr.io` 配置有读权限的 **Registry credential**。
3. **Render**：新建 **Web Service** → **Docker** → **Deploy an existing image**（不要选 Attach Git Repo 当构建源）。
   - Image URL：`ghcr.io/<你的 GitHub 用户名或组织>/<仓库名小写>/backend:latest`（或直接复制 Actions 日志里推送的 `:sha` 标签）。
   - **Start Command**（镜像已带默认 CMD，一般用下面覆盖以实现迁移）：`sh -lc "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port \"$PORT\" --workers 1"`
   - Health check path：`/api/health`，环境变量同上一节表格。
4. **每次 CI 打完新镜像**：在 Render Dashboard 对该服务 **Manual Deploy**，或在 GitHub 配置 **Deploy Hook**：仓库变量 `ENABLE_RENDER_DEPLOY_HOOK=true`，密钥 `RENDER_DEPLOY_HOOK_URL` = Render → Service → Manage → **Deploy Hook** 里的 URL。

> 若不使用 Deploy Hook，`latest` 标签被覆盖后需在 Render **主动再部署**，平台才会重新拉镜像。

---

## 项目结构

```
fomo/
├── frontend/                    # Next.js 14 前端
│   ├── app/
│   │   ├── pre-market/          # 盘前简讯页
│   │   ├── post-market/         # 盘后复盘页
│   │   ├── chat/                # RAG 对话页
│   │   ├── history/             # 历史简报页
│   │   ├── sources/             # 数据源配置页
│   │   └── prompts/             # Prompt 管理页
│   ├── components/
│   └── lib/
│       ├── api.ts               # 统一 API 层
│       └── useJobPoller.ts      # Job 状态轮询 Hook
│
├── backend/                     # Python FastAPI 后端
│   ├── pyproject.toml           # 依赖声明（uv）
│   ├── uv.lock                  # 锁定版本
│   ├── third_party/             # x-tweet-fetcher（git clone，默认不纳入版本库）
│   ├── agents/                  # 4 个 LangChain Agent
│   ├── api/                     # FastAPI 路由
│   ├── crawlers/                # 爬虫层（Twitter / 微信）
│   ├── db/                      # SQLAlchemy ORM（6 张表）
│   ├── pipeline/                # 全自动流水线编排
│   ├── scheduler/               # APScheduler 定时任务
│   ├── services/                # yfinance 股价 + 通知推送
│   ├── tools/                   # RAG 检索 Tool + DB 读写 Tool
│   └── vector_store/            # Chroma 向量库管理
│
├── docker-compose.yml
└── data/                        # 持久化数据（SQLite + Chroma）
```

---

## 数据库表说明

| 表名 | 用途 |
|------|------|
| `sources` | 数据源配置（博主/公众号） |
| `raw_articles` | 原始推文/文章（去重存储） |
| `reports` | 盘前/盘后 AI 简报 |
| `chat_history` | RAG 对话历史 |
| `pipeline_runs` | 流水线运行日志（Job 状态） |
| `prompts` | Agent Prompt 版本管理 |

---

## 定时任务时间表（美东时区）

| 任务 | 时间（ET）| 说明 |
|------|-----------|------|
| 盘前流水线 | 08:30 | 爬取 → 分析 → 生成盘前简报 |
| 盘后流水线 | 16:30 | 爬取 → 分析 → 生成盘后复盘 |

---

## 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` / `DB_*` | 数据库 ✅ | 见 `backend/.env.example`。 |
| `OPENAI_API_KEY` | ✅ | 网关 Key；向量可与 **`ARK_API_KEY`** 分拆。|
| **`LLM_CHAT_BASE_URL`** | ❌ | 对话根 URL；不配则用 **`OPENAI_BASE_URL`** → 方舟默认域名。|
| **`LLM_CHAT_MODEL`** | ❌ | 对话模型；不配则用 **`LLM_MODEL`**。|
| **`LLM_EMBED_BASE_URL`** | ❌ | 仅 **`EMBEDDING_PROVIDER=openai`** 等时用；**`ark`** 走 Ark SDK（默认 `…/api/v3`）。 |
| **`LLM_EMBED_MODEL`** | ❌ | ark/openai 时的 embedding 模型；不配用内置默认，亦兼容 **`ARK_EMBEDDING_MODEL`**。|
| **`ARK_API_BASE_URL`** | ❌ | 可选：传给 `Ark(base_url=…)` 的网关根路径（通常为 `…/api/v3`）；不配则用 SDK 自带北京域名。|
| **`LLM_LITE_BASE_URL`** / **`LLM_LITE_MODEL`** | ❌ | 轻量推理（情绪 / 热点）；不配则等同于对话。| 
| `EMBEDDING_PROVIDER` | ❌ | `local` / `openai` / `ark`。 |
| `ARK_EMBEDDING_DIMENSIONS`、`ARK_EMBEDDINGS_URL` … | ❌ | 维数默认与 pgvector **`1024`**；**`ARK_EMBEDDINGS_URL`** 兼容旧整条 multimodal URL，会自动归一为网关根。 |

**习惯写法**：对话仍可「Base + 模型」；向量在 **`EMBEDDING_PROVIDER=ark`** 时对齐官方示例：配置 **`ARK_API_KEY`（或与 LLM 共用 `OPENAI_API_KEY`）+ `LLM_EMBED_MODEL`** 即可。**本机向量**：`EMBEDDING_PROVIDER=local`。换向量维度/模型后请勿与旧 `article_chunks` 混用。

---

## 系统架构

```
定时任务 (APScheduler)
    │
    ├── 爬虫层 (Twitter / 微信)
    │       ↓ 清洗去重
    ├── SQLite (raw_articles)
    │       ↓ 向量化
    ├── Chroma (per-source collection)
    │       ↓
    ├── 情绪分析 Agent  →  RAG Tool → Chroma
    ├── 热点提取 Agent  →  RAG Tool → Chroma
    ├── 总结 Agent      →  RAG Tool + yfinance → Chroma
    │       ↓
    ├── SQLite (reports)
    │       ↓
    └── 通知推送 (Telegram / 企业微信)

前端 (Next.js)
    │
    ├── 盘前/盘后页  → GET /api/reports/latest
    ├── 历史简报页   → GET /api/reports
    ├── 数据源配置   → CRUD /api/sources + Job 轮询
    ├── Prompt 管理  → CRUD /api/prompts
    └── RAG 对话     → POST /api/chat/stream (SSE)
                              ↓
                    RAG 问答 Agent → Chroma
```
