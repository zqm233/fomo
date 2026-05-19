# FOMO — 常用：make install | make dev（提示）| make dev-backend | make dev-frontend | make up

.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := frontend

dev: ## 提示：本地需同时跑后端 + 前端（两个终端）
	@echo "本地全栈请开两个终端："
	@echo "  1) make dev-backend   → API http://localhost:8000"
	@echo "  2) make dev-frontend  → http://localhost:3000"

.PHONY: help install dev dev-backend dev-frontend up down \
        db-migrate db-upgrade db-rollback db-history db-current \
        akshare-smoke

help: ## 列出命令
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 环境文件占位、uv sync、npm install、预下载 Embedding 模型
	@test -f $(BACKEND_DIR)/.env || cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env
	@test -f $(FRONTEND_DIR)/.env.local || cp $(FRONTEND_DIR)/.env.local.example $(FRONTEND_DIR)/.env.local
	@mkdir -p data
	@command -v uv >/dev/null 2>&1 || { echo "请先安装 uv: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	cd $(BACKEND_DIR) && uv sync
	cd $(FRONTEND_DIR) && npm install
	@echo "→ 预下载 Embedding 模型（仅首次，已缓存则跳过）…"
	cd $(BACKEND_DIR) && uv run hf download BAAI/bge-m3 \
		--include "pytorch_model.bin" "*.json" "tokenizer*" "sentencepiece*" \
		&& echo "✓ 模型已就绪"

dev-backend: ## 启动 FastAPI（需先 install）
	@command -v uv >/dev/null 2>&1 || { echo "请先安装 uv: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	cd $(BACKEND_DIR) && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## 启动 Next.js（需先 install）
	cd $(FRONTEND_DIR) && npm run dev

up: ## Docker 前台启动全栈
	docker compose up --build

down: ## Docker 停止容器
	docker compose down

# ── DB 迁移 ────────────────────────────────────────────────────────────────────

db-migrate: ## 生成迁移文件并立即应用  用法: make db-migrate m="add_xxx_column"
	@test -n "$(m)" || { echo "用法: make db-migrate m=\"描述\""; exit 1; }
	cd $(BACKEND_DIR) && uv run alembic revision --autogenerate -m "$(m)" && uv run alembic upgrade head

db-upgrade: ## 仅应用已有迁移（不生成新文件）
	cd $(BACKEND_DIR) && uv run alembic upgrade head

db-rollback: ## 回滚最近一次迁移  用法: make db-rollback（默认 -1）
	cd $(BACKEND_DIR) && uv run alembic downgrade ${step:--1}

db-history: ## 查看迁移历史
	cd $(BACKEND_DIR) && uv run alembic history --verbose

db-current: ## 查看当前数据库版本
	cd $(BACKEND_DIR) && uv run alembic current

akshare-smoke: ## 测试 AkShare 新浪美股日线（可选: make akshare-smoke HIST=AAPL）
	cd $(BACKEND_DIR) && uv run python scripts/akshare_smoke.py $(if $(HIST),--hist $(HIST),)
