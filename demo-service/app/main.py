"""Orders API + health/logs/metrics for NEXUS's observability MCP server."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app import logbuf
from app.orders import compute_total, normalize_customer
from app.pipeline import run_forever

ORDERS: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_forever())
    yield
    task.cancel()


app = FastAPI(title="orders demo-service", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return logbuf.health()


@app.get("/metrics")
def metrics() -> dict:
    return dict(logbuf.METRICS)


@app.get("/logs")
def logs(limit: int = 50, level: str | None = None, contains: str | None = None) -> list[dict]:
    entries = list(logbuf.LOGS)
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    if contains:
        entries = [e for e in entries if contains.lower() in str(e).lower()]
    return entries[-limit:]


@app.post("/orders")
def create_order(order: dict) -> dict:
    if not order.get("items"):
        raise HTTPException(422, "order needs items")
    oid = order.get("id") or f"api-{len(ORDERS) + 1}"
    ORDERS[oid] = {**order, "id": oid, "customer": normalize_customer(order), **compute_total(order)}
    return ORDERS[oid]


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    if order_id not in ORDERS:
        raise HTTPException(404, "not found")
    return ORDERS[order_id]
