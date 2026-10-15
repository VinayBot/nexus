"""Order business logic."""

from app.config import DISCOUNTS, FREE_SHIPPING_OVER, SHIPPING_FEE, TAX_RATE


def normalize_customer(order: dict) -> dict:
    """Customer fields used for receipts; guest orders have no email."""
    email = (order.get("email") or "").strip().lower()
    name = (order.get("name") or "Guest").strip()
    return {"email": email, "name": name, "guest": not email}


def line_total(item: dict) -> float:
    qty = int(item.get("qty") or 1)
    return round(float(item["price"]) * qty, 2)


def apply_discount(subtotal: float, code: str | None) -> float:
    rate = DISCOUNTS.get((code or "").strip().upper(), 0.0)
    return round(subtotal * (1 - rate), 2)


def compute_total(order: dict) -> dict:
    subtotal = round(sum(line_total(i) for i in order["items"]), 2)
    discounted = apply_discount(subtotal, order.get("discount_code"))
    shipping = 0.0 if discounted >= FREE_SHIPPING_OVER else SHIPPING_FEE
    tax = round(discounted * TAX_RATE, 2)
    return {
        "subtotal": subtotal,
        "discounted": discounted,
        "shipping": shipping,
        "tax": tax,
        "total": round(discounted + shipping + tax, 2),
    }


def paginate(items: list, page: int, size: int) -> list:
    """Return one page (1-based) of ``size`` items."""
    start = (page - 1) * size
    end = start + size
    return items[start:end]
