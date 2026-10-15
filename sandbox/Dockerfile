# Isolated test runner used by the sandbox-exec MCP server.
# Runs with --network none, 1 CPU, 512 MB, a pids limit and a hard timeout.
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2 fastapi==0.115.12 httpx==0.28.1 pydantic==2.11.7 \
    && useradd -m sandbox
USER sandbox
WORKDIR /work
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-m", "pytest", "-q"]
