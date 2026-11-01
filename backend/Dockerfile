FROM python:3.15-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nexus
WORKDIR /app/backend
# dependencies first (cached layer), then the code
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres --no-install-project
COPY backend/ ./
COPY demo-service/ /app/demo-service/
COPY docs/ /app/docs/
RUN uv sync --frozen --no-dev --extra postgres && mkdir -p /app/backend/data && chown -R nexus:nexus /app
# git commits fixes on demo-service branches; the container user needs an identity
RUN git config --system user.name "NEXUS" && git config --system user.email "nexus@localhost"
USER nexus
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1
CMD ["uv", "run", "--no-sync", "uvicorn", "nexus.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
