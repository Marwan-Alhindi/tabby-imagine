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
from datetime import date, timedelta
from typing import Literal, Optional
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from . import db

Category = Literal["mobiles", "electronics", "travel", "spa_salon", "fashion", "beauty"]
Plan = Literal["split_in_4", "pay_in_6", "pay_in_12"]


def emit(event: dict) -> None:
    """Send a UI event to the frontend (no-op outside a graph run)."""
    try:
        get_stream_writer()(event)
    except RuntimeError:
        pass


# Tabby payment rules shown in the app.
SPLIT_IN_4_MAX = 5000                    # pay in 4, interest-free
LONG_PLAN_MIN, LONG_PLAN_MAX = 500, 50000
LONG_PLAN_FEE_PCT = {6: 0.0, 12: 8.0}    # illustrative


def _card(p: dict) -> dict:
    """What the frontend renders (a product_cards row plus the cheapest monthly amount)."""
    return {**p, "monthly_from": _cheapest_monthly(p["price"])}


def _brief(p: dict) -> dict:
    """What the model sees: enough to reason and refer back by id."""
    b = {"id": p["id"], "name": p["name"], "price": p["price"], "rating": p["rating"], "store": p["store_name"]}
    if p["original_price"]:
        b["was"] = p["original_price"]
    b.update(p["specs"])
    return b


def plan_options(price: float) -> list[dict]:
    opts = []
    if price <= SPLIT_IN_4_MAX:
        opts.append({"plan": "split_in_4", "label": "Split in 4, interest-free",
                     "installments": 4, "per_installment": round(price / 4, 2), "fee_pct": 0.0})
    if LONG_PLAN_MIN <= price <= LONG_PLAN_MAX:
        for m, fee in LONG_PLAN_FEE_PCT.items():
            total = price * (1 + fee / 100)
            opts.append({"plan": f"pay_in_{m}", "label": f"Pay monthly over {m} months",
                         "installments": m, "per_installment": round(total / m, 2), "fee_pct": fee})
    return opts


def _cheapest_monthly(price: float) -> Optional[float]:
    opts = plan_options(price)
    return min(o["per_installment"] for o in opts) if opts else None


def payments_summary() -> dict:
    orders = db.list_orders()
    account = db.get_account()
    upcoming = sorted(
        ({**i, "order_id": o["id"], "product": o["product"], "store": o["store"]}
         for o in orders for i in o["installments"] if i["status"] != "paid"),
        key=lambda i: i["due"],
    )
    horizon = str(date.today() + timedelta(days=30))
    outstanding = round(sum(i["amount"] for i in upcoming), 2)
    return {
        "due_in_30_days": round(sum(i["amount"] for i in upcoming if i["due"] <= horizon), 2),
        "total_outstanding": outstanding,
        "available_limit": round(account["credit_limit"] - outstanding, 2),
        "upcoming": upcoming,
        "orders": orders,
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
    sort: Literal["relevance", "price_asc", "price_desc", "rating", "discount"] = "relevance"
    limit: int = Field(6, ge=1, le=12)


@tool(args_schema=SearchProductsArgs)
def search_products(limit: int = 6, **filters) -> str:
    """Search Tabby's product catalog with filters. Results are shown to the user as product cards."""
    res = db.search_products(limit=limit, **filters)
    emit({"type": "products", "filters": {k: v for k, v in filters.items() if v not in (None, False, "relevance")},
          "total": res["total"], "items": [_card(p) for p in res["items"]]})
    return json.dumps({"total_matches": res["total"], "shown": [_brief(p) for p in res["items"]]})


@tool
def get_deals(category: Optional[Category] = None, limit: int = 6) -> str:
    """List current discounted items, biggest discount first. Shown as product cards."""
    res = db.search_products(limit=limit, category=category, deals_only=True, sort="discount")
    emit({"type": "products", "filters": {"deals_only": True, "category": category},
          "total": res["total"], "items": [_card(p) for p in res["items"]]})
    return json.dumps([_brief(p) for p in res["items"]])


@tool
def search_stores(query: Optional[str] = None, category: Optional[Category] = None) -> str:
    """Find partner stores that accept Tabby, by name or category, with their cashback rate."""
    stores = db.list_stores(query, category)
    emit({"type": "stores", "items": stores})
    return json.dumps(stores)


@tool
def compare_products(product_ids: list[str]) -> str:
    """Compare 2-4 products side by side (price, specs, plans). Use ids from earlier results."""
    items = db.get_products(product_ids)
    if len(items) < 2:
        return "Need at least two valid product ids."
    emit({"type": "comparison", "items": [_card(p) for p in items]})
    return json.dumps([{**_brief(p), "plans": plan_options(p["price"])} for p in items])


@tool
def get_payment_plans(price: Optional[float] = None, product_id: Optional[str] = None) -> str:
    """Show which Tabby plans (split in 4, 6 or 12 months) apply to a price or product, and the installment amounts."""
    if product_id:
        p = db.get_product(product_id)
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
    a = db.get_account()
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
    r = db.get_account()["referral"]
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
    p = db.get_product(product_id)
    if not p:
        return f"Unknown product id {product_id}."
    opt = next((o for o in plan_options(p["price"]) if o["plan"] == plan), None)
    if not opt:
        return f"{plan} is not available for {p['price']} SAR. Available: {[o['plan'] for o in plan_options(p['price'])]}"
    available = payments_summary()["available_limit"]
    if p["price"] > available:
        return f"Over the available limit ({available:.0f} SAR). Suggest a cheaper item or paying down the balance."

    store = p["store_name"]
    if not confirm("checkout", f"Buy {p['name']}", [
        ("Store", store),
        ("Price", f"{p['price']:,.0f} SAR"),
        ("Plan", opt["label"]),
        ("Today", f"{opt['per_installment']:,.2f} SAR"),
        ("Then", f"{opt['installments'] - 1} x {opt['per_installment']:,.2f} SAR monthly"),
    ], "Confirm purchase"):
        return "User cancelled the purchase. Nothing was charged."

    oid = f"ord_{uuid4().hex[:6]}"
    t = date.today()
    installments = [{"id": f"ins_{oid}_{n + 1}", "order_id": oid, "seq": n + 1, "amount": opt["per_installment"],
                     "due": str(t + timedelta(days=30 * n)), "status": "paid" if n == 0 else "upcoming"}
                    for n in range(opt["installments"])]
    order = {"id": oid, "product": p["name"], "store": store, "total": p["price"], "plan": plan}
    db.create_order(order, installments)
    emit({"type": "receipt", "title": "Order placed", "order": order})
    return json.dumps({"status": "placed", "order_id": oid, "first_payment": opt["per_installment"]})


@tool
def pay_installment(installment_id: str) -> str:
    """Pay one upcoming installment early (ids come from get_payments). Requires the user's confirmation in the app."""
    i = db.get_installment(installment_id)
    if not i:
        return f"Unknown installment id {installment_id}."
    if i["status"] == "paid":
        return "Already paid."
    o = i["orders"]
    if not confirm("pay_installment", f"Pay {i['amount']:,.2f} SAR now", [
        ("For", f"{o['product']} ({o['store']})"),
        ("Originally due", i["due"]),
        ("Card", "Mada •••• 4821"),
    ], "Pay now"):
        return "User cancelled. Nothing was paid."
    db.mark_installment_paid(installment_id)
    emit({"type": "receipt", "title": "Payment successful", "order": o})
    return json.dumps({"status": "paid", "remaining_outstanding": payments_summary()["total_outstanding"]})


@tool
def update_home_address(city: str, district: str, street: str, building_number: Optional[str] = None) -> str:
    """Save the user's home address to their profile. Requires confirmation in the app."""
    addr = {"city": city, "district": district, "street": street, "building_number": building_number}
    if not confirm("update_address", "Save home address", [
        ("City", city), ("District", district), ("Street", street), ("Building", building_number or "-"),
    ], "Save"):
        return "User cancelled. Address not saved."
    db.update_account({"home_address": addr,
                       "profile_completion_pct": min(100, db.get_account()["profile_completion_pct"] + 30)})
    emit({"type": "receipt", "title": "Address saved", "address": addr})
    return "Saved."


READ_TOOLS = [search_products, get_deals, search_stores, compare_products,
              get_payment_plans, get_payments, get_account]
UI_TOOLS = [open_screen, share_referral]
ACTION_TOOLS = [start_checkout, pay_installment, update_home_address]
ALL_TOOLS = READ_TOOLS + UI_TOOLS + ACTION_TOOLS
