# FOMO — 美股财经投研 AI Agent 系统

> 个人投研 + AI Agent 求职作品集项目

基于 LangChain + FastAPI + Next.js 的全栈 AI 投研系统，自动爬取推特财经博主和微信公众号文章，通过向量知识库和大模型生成每日盘前/盘后简报，并提供 RAG 对话窗口。

---

## 功能亮点

| 功能 | 说明 |
|------|------|
| 自动爬取 | 推特 (x-tweet-fetcher) + 微信公众号，定时爬取 |
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
- **后端**：Python FastAPI · LangChain · APScheduler
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

### 3. 启动后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

后端启动后访问 API 文档：http://localhost:8000/docs

### 4. 启动前端

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

前端访问：http://localhost:3000

---

## Docker 一键部署

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env

# 2. 创建数据目录
mkdir -p data

# 3. 启动
docker compose up --build -d

# 查看日志
docker compose logs -f
```

服务地址：
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

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
| `OPENAI_API_KEY` | ✅ | OpenAI API Key |
| `OPENAI_BASE_URL` | ❌ | 代理地址（可选） |
| `LLM_MODEL` | ❌ | 默认 `gpt-4o-mini` |
| `TWITTER_FETCHER_PATH` | ❌ | x-tweet-fetcher 目录路径 |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram 推送（留空不推送） |
| `WECOM_WEBHOOK_URL` | ❌ | 企业微信推送（留空不推送） |

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
