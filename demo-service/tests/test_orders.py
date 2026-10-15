import asyncio

from app.config import TAX_RATE
from app.inventory import stock_level
from app.orders import apply_discount, compute_total, normalize_customer, paginate


def test_guest_orders_have_no_email():
    assert normalize_customer({"email": None}) == {"email": "", "name": "Guest", "guest": True}


def test_customer_email_is_normalised():
    assert normalize_customer({"email": " Bob@Example.COM ", "name": "Bob"})["email"] == "bob@example.com"


def test_discount_codes_are_case_insensitive():
    assert apply_discount(100.0, "save10") == 90.0
    assert apply_discount(100.0, None) == 100.0


def test_tax_rate_is_a_fraction():
    assert 0 < TAX_RATE < 1


def test_total_includes_tax_and_shipping():
    t = compute_total({"items": [{"price": 10.0, "qty": 2}], "discount_code": None})
    assert t == {"subtotal": 20.0, "discounted": 20.0, "shipping": 4.99, "tax": 1.6, "total": 26.59}


def test_paginate_returns_full_pages():
    items = list(range(12))
    assert paginate(items, 1, 5) == [0, 1, 2, 3, 4]
    assert paginate(items, 2, 5) == [5, 6, 7, 8, 9]
    assert paginate(items, 3, 5) == [10, 11]


def test_inventory_answers_within_timeout():
    assert asyncio.run(stock_level("tea")) == 40


def test_pipeline_orders_are_processable():
    """Every generated order shape (guests, discount codes, SKUs) must process."""
    from app.pipeline import make_order, process

    async def run():
        for n in range(1, 7):
            await process(make_order(n))

    asyncio.run(asyncio.wait_for(run(), timeout=5))
