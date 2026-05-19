FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependency layer cache
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY . .

# Re-sync after app sources; verify console scripts exist (avoids Render "uvicorn: not found")
RUN uv sync --frozen --no-dev --no-cache \
    && test -x /app/.venv/bin/uvicorn \
    && test -x /app/.venv/bin/alembic

RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000

# Use absolute paths — Render custom commands may not inherit venv PATH.
CMD ["/app/scripts/docker-entrypoint.sh"]
