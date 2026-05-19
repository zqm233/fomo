FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependency layer cache
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Render (and similar) inject PORT at runtime; local compose keeps default 8000.
CMD sh -lc 'exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1'
