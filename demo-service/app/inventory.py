"""Simulated inventory dependency (a remote call in real life)."""

import asyncio

from app.config import INVENTORY_TIMEOUT_S

SIMULATED_LATENCY_S = 0.02
STOCK = {"tea": 40, "mug": 12, "kettle": 5, "matcha": 25, "whisk": 9}


async def _remote_stock(sku: str) -> int:
    await asyncio.sleep(SIMULATED_LATENCY_S)
    return STOCK.get(sku, 0)


async def stock_level(sku: str) -> int:
    """Stock for a SKU; raises TimeoutError if the dependency is too slow."""
    return await asyncio.wait_for(_remote_stock(sku), timeout=INVENTORY_TIMEOUT_S)
