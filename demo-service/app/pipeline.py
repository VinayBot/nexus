"""Background order pipeline: processes a batch of generated orders every second.

It deliberately exercises every code path (guest orders, discount codes, pages,
inventory checks) and checks invariants, so a bug shows up in logs and health
within seconds.
"""

import asyncio
import itertools
import time

from app.config import PAGE_SIZE
from app.inventory import stock_level
from app.logbuf import log, record
from app.orders import compute_total, normalize_customer, paginate

SKUS = [("tea", 6.5), ("mug", 12.0), ("kettle", 39.0), ("matcha", 18.0), ("whisk", 9.5)]
CODES = [None, "SAVE10", "save10", "VIP20", ""]
_counter = itertools.count(1)


def make_order(n: int) -> dict:
    sku, price = SKUS[n % len(SKUS)]
    return {
        "id": f"o-{n}",
        "email": None if n % 3 == 0 else f"Buyer{n}@Example.com ",
        "name": None if n % 4 == 0 else f"Buyer {n}",
        "items": [{"sku": sku, "price": price, "qty": 1 + n % 3}],
        "discount_code": CODES[n % len(CODES)],
    }


async def process(order: dict) -> dict:
    customer = normalize_customer(order)
    totals = compute_total(order)
    if totals["total"] > totals["subtotal"] * 2 + 10:
        raise ValueError(f"implausible total {totals['total']} for subtotal {totals['subtotal']} (check TAX_RATE)")
    for item in order["items"]:
        await stock_level(item["sku"])
    return {"id": order["id"], "customer": customer, **totals}


async def run_batch() -> None:
    orders = [make_order(next(_counter)) for _ in range(PAGE_SIZE * 2)]
    page = paginate(orders, 2, PAGE_SIZE)
    if len(page) != PAGE_SIZE:
        log("ERROR", "pipeline.invariant", f"paginate() returned {len(page)} orders for a page of {PAGE_SIZE}", function="paginate", file="app/orders.py")
        record(False, 0.0)
    for order in orders:
        started = time.perf_counter()
        try:
            await process(order)
            record(True, (time.perf_counter() - started) * 1000)
        except Exception as exc:
            record(False, (time.perf_counter() - started) * 1000)
            log("ERROR", "order.failed", f"{type(exc).__name__}: {exc}", exc=exc, order_id=order["id"])


async def run_forever(interval_s: float = 1.0) -> None:
    log("INFO", "pipeline.started", "order pipeline running")
    while True:
        try:
            await run_batch()
        except Exception as exc:  # the pipeline itself must never die
            log("ERROR", "pipeline.crashed", str(exc), exc=exc)
        await asyncio.sleep(interval_s)
