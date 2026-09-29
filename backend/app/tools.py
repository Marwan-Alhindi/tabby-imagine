"""Tools the assistant can use, grouped by what they touch.

Read tools    search the catalog / account and render cards in the chat.
UI tools      drive the app itself (open a tab with filters applied).
Action tools  change money or personal data. Each one pauses the graph with
              `interrupt()` and only continues after the user taps Confirm in
              the app. The model cannot approve on the user's behalf: approval
              arrives through a separate endpoint, never through chat text.

Every tool returns a compact JSON string for the model and, separately, pushes
a rich `ui` event to the frontend through LangGraph's custom stream.
"""

import json
from datetime import timedelta
from typing import Literal, Optional
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from . import data

Category = Literal["mobiles", "electronics", "travel", "spa_salon", "fashion", "beauty"]
Plan = Literal["split_in_4", "pay_in_6", "pay_in_12"]


def emit(event: dict) -> None:
    """Send a UI event to the frontend (no-op outside a graph run)."""
    try:
        get_stream_writer()(event)
    except RuntimeError:
        pass


def _card(p: dict) -> dict:
    store = data.STORES_BY_ID[p["store"]]
    return {**p, "store_name": store["name"], "cashback_pct": store["cashback_pct"],
            "monthly_from": _cheapest_monthly(p["price"])}


def _brief(p: dict) -> dict:
    """What the model sees: enough to reason and refer back by id."""
    b = {k: p[k] for k in ("id", "name", "price", "rating")}
    b["store"] = data.STORES_BY_ID[p["store"]]["name"]
    if p["original_price"]:
        b["was"] = p["original_price"]
    b.update(p["specs"])
    return b


# ---------------------------------------------------------------- search core

def filter_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    brands: Optional[list[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_storage_gb: Optional[int] = None,
    color: Optional[str] = None,
    store: Optional[str] = None,
    deals_only: bool = False,
    sort_by: str = "relevance",
) -> list[dict]:
    items = data.PRODUCTS
    if category:
        items = [p for p in items if p["category"] == category]
    if brands:
        wanted = {b.lower() for b in brands}
        items = [p for p in items if p["brand"].lower() in wanted]
    if min_price is not None:
        items = [p for p in items if p["price"] >= min_price]
    if max_price is not None:
        items = [p for p in items if p["price"] <= max_price]
    if min_storage_gb:
        items = [p for p in items if p["specs"].get("storage_gb", 0) >= min_storage_gb]
    if color:
        items = [p for p in items if color.lower() in p["specs"].get("color", "").lower()]
    if store:
        s = store.lower()
        items = [p for p in items if s in p["store"] or s in data.STORES_BY_ID[p["store"]]["name"].lower()]
    if deals_only:
        items = [p for p in items if p["original_price"]]
    if query:
        words = query.lower().split()
        def score(p):
            hay = " ".join([p["name"], p["brand"], p["store"], json.dumps(p["specs"])]).lower()
            return sum(w in hay for w in words)
        items = [p for p in items if score(p) > 0]
        if sort_by == "relevance":
            items = sorted(items, key=score, reverse=True)
    if sort_by == "price_asc":
        items = sorted(items, key=lambda p: p["price"])
    elif sort_by == "price_desc":
        items = sorted(items, key=lambda p: -p["price"])
    elif sort_by == "rating":
        items = sorted(items, key=lambda p: -p["rating"])
    elif sort_by == "discount":
        items = sorted(items, key=lambda p: -((p["original_price"] or p["price"]) - p["price"]))
    return items


def plan_options(price: float) -> list[dict]:
    opts = []
    if price <= data.SPLIT_IN_4_MAX:
        opts.append({"plan": "split_in_4", "label": "Split in 4, interest-free",
                     "installments": 4, "per_installment": round(price / 4, 2), "fee_pct": 0.0})
    if data.LONG_PLAN_MIN <= price <= data.LONG_PLAN_MAX:
        for m in data.LONG_PLAN_MONTHS:
            fee = data.LONG_PLAN_FEE_PCT[m]
            total = price * (1 + fee / 100)
            opts.append({"plan": f"pay_in_{m}", "label": f"Pay monthly over {m} months",
                         "installments": m, "per_installment": round(total / m, 2), "fee_pct": fee})
    return opts


def _cheapest_monthly(price: float) -> Optional[float]:
    opts = plan_options(price)
    return min(o["per_installment"] for o in opts) if opts else None


def outstanding() -> float:
    return round(sum(i["amount"] for o in data.ORDERS for i in o["installments"]
                     if i["status"] != "paid"), 2)


def payments_summary() -> dict:
    upcoming = sorted(
        ({**i, "order_id": o["id"], "product": o["product"], "store": o["store"]}
         for o in data.ORDERS for i in o["installments"] if i["status"] != "paid"),
        key=lambda i: i["due"],
    )
    due_30 = [i for i in upcoming if i["due"] <= str(data.today() + timedelta(days=30))]
    return {
        "due_in_30_days": round(sum(i["amount"] for i in due_30), 2),
        "total_outstanding": outstanding(),
        "available_limit": round(data.ACCOUNT["credit_limit"] - outstanding(), 2),
        "upcoming": upcoming,
        "orders": data.ORDERS,
    }


# ---------------------------------------------------------------- read tools

class SearchProductsArgs(BaseModel):
    query: Optional[str] = Field(None, description="Free-text keywords in English, e.g. 'iphone pro' or 'massage'. Leave empty when structured filters are enough.")
    category: Optional[Category] = Field(None, description="Catalog category.")
    brands: Optional[list[str]] = Field(None, description="Brand names, e.g. ['Apple', 'Samsung'].")
    min_price: Optional[float] = Field(None, description="Minimum price in SAR.")
    max_price: Optional[float] = Field(None, description="Maximum price in SAR. If the user gives a monthly budget, convert it: split_in_4 max = 4 x monthly; 12-month max = 12 x monthly / 1.08.")
    min_storage_gb: Optional[int] = Field(None, description="Minimum storage in GB (phones, laptops, tablets).")
    color: Optional[str] = Field(None, description="Color keyword, e.g. 'blue'.")
    store: Optional[str] = Field(None, description="Store id or name, e.g. 'jarir', 'noon'.")
    deals_only: bool = Field(False, description="Only discounted items.")
    sort_by: Literal["relevance", "price_asc", "price_desc", "rating", "discount"] = "relevance"
    limit: int = Field(6, ge=1, le=12)


@tool(args_schema=SearchProductsArgs)
def search_products(limit: int = 6, **filters) -> str:
    """Search Tabby's product catalog with filters. Results are shown to the user as product cards."""
    items = filter_products(**filters)
    emit({"type": "products", "filters": {k: v for k, v in filters.items() if v not in (None, False, "relevance")},
          "total": len(items), "items": [_card(p) for p in items[:limit]]})
    return json.dumps({"total_matches": len(items), "shown": [_brief(p) for p in items[:limit]]})


@tool
def get_deals(category: Optional[Category] = None, limit: int = 6) -> str:
    """List current discounted items, biggest discount first. Shown as product cards."""
    items = filter_products(category=category, deals_only=True, sort_by="discount")
    emit({"type": "products", "filters": {"deals_only": True, "category": category},
          "total": len(items), "items": [_card(p) for p in items[:limit]]})
    return json.dumps([_brief(p) for p in items[:limit]])


@tool
def search_stores(query: Optional[str] = None, category: Optional[Category] = None) -> str:
    """Find partner stores that accept Tabby, by name or category, with their cashback rate."""
    stores = data.STORES
    if category:
        stores = [s for s in stores if category in s["categories"]]
    if query:
        q = query.lower()
        stores = [s for s in stores if q in s["name"].lower() or q in s["id"]]
    emit({"type": "stores", "items": stores})
    return json.dumps(stores)


@tool
def compare_products(product_ids: list[str]) -> str:
    """Compare 2-4 products side by side (price, specs, plans). Use ids from earlier results."""
    items = [data.PRODUCTS_BY_ID[i] for i in product_ids if i in data.PRODUCTS_BY_ID]
    if len(items) < 2:
        return "Need at least two valid product ids."
    emit({"type": "comparison", "items": [_card(p) for p in items]})
    return json.dumps([{**_brief(p), "plans": plan_options(p["price"])} for p in items])


@tool
def get_payment_plans(price: Optional[float] = None, product_id: Optional[str] = None) -> str:
    """Show which Tabby plans (split in 4, 6 or 12 months) apply to a price or product, and the installment amounts."""
    if product_id:
        p = data.PRODUCTS_BY_ID.get(product_id)
        if not p:
            return f"Unknown product id {product_id}."
        price, name = p["price"], p["name"]
    elif price is None:
        return "Give a price or a product_id."
    else:
        name = None
    opts = plan_options(price)
    emit({"type": "plans", "price": price, "product": name, "options": opts})
    return json.dumps({"price": price, "options": opts or "No plan available for this amount."})


@tool
def get_payments() -> str:
    """The user's upcoming installments, amount due in 30 days, outstanding balance, and available spending limit."""
    s = payments_summary()
    emit({"type": "payments", **s})
    return json.dumps({k: s[k] for k in ("due_in_30_days", "total_outstanding", "available_limit", "upcoming")})


@tool
def get_account() -> str:
    """The user's profile: name, missing profile items, cashback balance, and referral reward."""
    a = data.ACCOUNT
    todo = [t for t, missing in [("Add home address", not a["home_address"]),
                                 ("Complete profile", a["profile_completion_pct"] < 100)] if missing]
    emit({"type": "account", **a, "todo": todo})
    return json.dumps({**a, "todo": todo})


# ---------------------------------------------------------------- UI tools

@tool
def open_screen(
    screen: Literal["home", "shop", "payments", "profile"],
    category: Optional[Category] = None,
    filters: Optional[dict] = None,
) -> str:
    """Navigate the app to a tab. For 'shop', pass category and the same filters used in search_products so the user lands on the filtered list."""
    emit({"type": "navigate", "screen": screen, "category": category, "filters": filters or {}})
    return f"Opened {screen}."


@tool
def share_referral() -> str:
    """Give the user their personal invite link to share with friends."""
    r = data.ACCOUNT["referral"]
    link = f"https://tabby.sa/invite/{r['code']}"
    emit({"type": "referral", "link": link, **r})
    return json.dumps({"link": link, **r})


# ---------------------------------------------------------------- action tools

def confirm(action: str, title: str, lines: list[tuple[str, str]], confirm_label: str) -> bool:
    """Pause the graph until the user taps Confirm or Cancel in the app."""
    answer = interrupt({"action": action, "title": title, "lines": lines, "confirm_label": confirm_label})
    return bool(answer and answer.get("approved"))


@tool
def start_checkout(product_id: str, plan: Plan) -> str:
    """Buy a product with a Tabby plan. The user must confirm in the app before anything is charged."""
    p = data.PRODUCTS_BY_ID.get(product_id)
    if not p:
        return f"Unknown product id {product_id}."
    opt = next((o for o in plan_options(p["price"]) if o["plan"] == plan), None)
    if not opt:
        return f"{plan} is not available for {p['price']} SAR. Available: {[o['plan'] for o in plan_options(p['price'])]}"
    available = data.ACCOUNT["credit_limit"] - outstanding()
    if p["price"] > available:
        return f"Over the available limit ({available:.0f} SAR). Suggest a cheaper item or paying down the balance."

    store = data.STORES_BY_ID[p["store"]]["name"]
    if not confirm("checkout", f"Buy {p['name']}", [
        ("Store", store),
        ("Price", f"{p['price']:,.0f} SAR"),
        ("Plan", opt["label"]),
        ("Today", f"{opt['per_installment']:,.2f} SAR"),
        ("Then", f"{opt['installments'] - 1} x {opt['per_installment']:,.2f} SAR monthly"),
    ], "Confirm purchase"):
        return "User cancelled the purchase. Nothing was charged."

    oid = f"ord_{uuid4().hex[:6]}"
    t = data.today()
    installments = [{"id": f"ins_{oid}_{n + 1}", "amount": opt["per_installment"],
                     "due": str(t + timedelta(days=30 * n)), "status": "paid" if n == 0 else "upcoming"}
                    for n in range(opt["installments"])]
    order = {"id": oid, "product": p["name"], "store": store, "total": p["price"],
             "plan": plan, "installments": installments}
    data.ORDERS.append(order)
    emit({"type": "receipt", "title": "Order placed", "order": order})
    return json.dumps({"status": "placed", "order_id": oid, "first_payment": opt["per_installment"]})


@tool
def pay_installment(installment_id: str) -> str:
    """Pay one upcoming installment early (ids come from get_payments). Requires the user's confirmation in the app."""
    for o in data.ORDERS:
        for i in o["installments"]:
            if i["id"] == installment_id:
                if i["status"] == "paid":
                    return "Already paid."
                if not confirm("pay_installment", f"Pay {i['amount']:,.2f} SAR now", [
                    ("For", f"{o['product']} ({o['store']})"),
                    ("Originally due", i["due"]),
                    ("Card", "Mada •••• 4821"),
                ], "Pay now"):
                    return "User cancelled. Nothing was paid."
                i["status"] = "paid"
                emit({"type": "receipt", "title": "Payment successful", "order": o})
                return json.dumps({"status": "paid", "remaining_outstanding": outstanding()})
    return f"Unknown installment id {installment_id}."


@tool
def update_home_address(city: str, district: str, street: str, building_number: Optional[str] = None) -> str:
    """Save the user's home address to their profile. Requires confirmation in the app."""
    addr = {"city": city, "district": district, "street": street, "building_number": building_number}
    if not confirm("update_address", "Save home address", [
        ("City", city), ("District", district), ("Street", street), ("Building", building_number or "-"),
    ], "Save"):
        return "User cancelled. Address not saved."
    data.ACCOUNT["home_address"] = addr
    data.ACCOUNT["profile_completion_pct"] = min(100, data.ACCOUNT["profile_completion_pct"] + 30)
    emit({"type": "receipt", "title": "Address saved", "address": addr})
    return "Saved."


READ_TOOLS = [search_products, get_deals, search_stores, compare_products,
              get_payment_plans, get_payments, get_account]
UI_TOOLS = [open_screen, share_referral]
ACTION_TOOLS = [start_checkout, pay_installment, update_home_address]
ALL_TOOLS = READ_TOOLS + UI_TOOLS + ACTION_TOOLS
