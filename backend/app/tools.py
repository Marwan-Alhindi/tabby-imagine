"""Tools the assistant can use, grouped by what they touch.

Read tools    search the catalog / account and render cards in the chat.
UI tools      drive the app itself (open a tab with filters applied).
Action tools  change money, cards or personal data. Each one pauses the graph with
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


def _option(plan: str, label: str, price: float, n: int, fee_pct: float) -> dict:
    total = round(price * (1 + fee_pct / 100), 2)
    per = round(total / n, 2)
    today = date.today()
    return {"plan": plan, "label": label, "installments": n, "per_installment": per, "fee_pct": fee_pct,
            "fee_amount": round(total - price, 2), "total": total,
            "schedule": [{"n": k + 1, "due": str(today + timedelta(days=30 * k)), "amount": per} for k in range(n)]}


def plan_options(price: float) -> list[dict]:
    """Plans a price qualifies for. First payment is today, the rest every 30 days."""
    opts = []
    if price <= SPLIT_IN_4_MAX:
        opts.append(_option("split_in_4", "Split in 4, interest-free", price, 4, 0.0))
    if LONG_PLAN_MIN <= price <= LONG_PLAN_MAX:
        for m, fee in LONG_PLAN_FEE_PCT.items():
            opts.append(_option(f"pay_in_{m}", f"Pay monthly over {m} months", price, m, fee))
    return opts


def _plan_brief(o: dict) -> dict:
    return {k: o[k] for k in ("plan", "label", "installments", "per_installment", "fee_amount", "total")}


def _cheapest_monthly(price: float) -> Optional[float]:
    opts = plan_options(price)
    return min(o["per_installment"] for o in opts) if opts else None


def order_progress(o: dict) -> dict:
    """Where an order's plan stands: paid vs left, next and final due dates."""
    ins = o["installments"]
    left = [i for i in ins if i["status"] != "paid"]
    today = str(date.today())
    return {
        "order_id": o["id"], "product": o["product"], "store": o["store"], "plan": o["plan"], "total": o["total"],
        "installments_total": len(ins), "installments_paid": len(ins) - len(left), "installments_left": len(left),
        "amount_paid": round(sum(i["amount"] for i in ins if i["status"] == "paid"), 2),
        "amount_left": round(sum(i["amount"] for i in left), 2),
        "next_due": left[0]["due"] if left else None,
        "final_due": left[-1]["due"] if left else None,
        "overdue": [i for i in left if i["due"] < today],
        "installments": ins,
    }


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
        "overdue": [i for i in upcoming if i["due"] < str(date.today())],
        "upcoming": upcoming,
        "orders": [order_progress(o) for o in orders],
    }


FAILURE_REASONS = {
    "expired_card": "The card has expired.",
    "insufficient_funds": "The bank reported insufficient balance.",
    "do_not_honor": "The bank declined without a reason; online payments may be blocked on the card.",
    "3ds_failed": "OTP / 3-D Secure verification failed or timed out.",
}
BRAND_NAMES = {"visa": "Visa", "mastercard": "Mastercard", "mada": "mada", "apple_pay": "Apple Pay"}


def card_label(m: dict) -> str:
    return f"{BRAND_NAMES[m['brand']]} •••• {m['last4']}"


def with_status(m: dict) -> dict:
    t = date.today()
    expired = (m["exp_year"], m["exp_month"]) < (t.year, t.month)
    return {**m, "label": card_label(m), "expiry": f"{m['exp_month']:02d}/{m['exp_year']}",
            "status": "expired" if expired else "active"}


def default_card() -> Optional[dict]:
    return next((with_status(m) for m in db.list_payment_methods() if m["is_default"]), None)


def purchase_checks(price: float) -> list[dict]:
    """Everything that decides whether a purchase at this price would go through."""
    s = payments_summary()
    account = db.get_account()
    card = default_card()
    return [
        {"check": "Amount has a Tabby plan", "ok": bool(plan_options(price)),
         "detail": f"Split in 4 up to {SPLIT_IN_4_MAX:,} SAR; monthly {LONG_PLAN_MIN:,}-{LONG_PLAN_MAX:,} SAR"},
        {"check": "Within available limit", "ok": price <= s["available_limit"],
         "detail": f"{s['available_limit']:,.2f} SAR available of {account['credit_limit']:,.0f}"},
        {"check": "No overdue payments", "ok": not s["overdue"],
         "detail": f"{len(s['overdue'])} overdue" if s["overdue"] else "All payments on time"},
        {"check": "Default card can be charged", "ok": bool(card) and card["status"] == "active",
         "detail": f"{card['label']} ({card['status']})" if card else "No default card"},
        {"check": "Identity verified", "ok": account["id_verified"], "detail": "Verified" if account["id_verified"] else "Pending"},
    ]


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
    """Show the Tabby plans for a product or price: installment amount, number of payments, fees, total paid, and the payment dates. For a product, the user can pick a plan and pay from the card."""
    name = None
    if product_id:
        p = db.get_product(product_id)
        if not p:
            return f"Unknown product id {product_id}."
        price, name = p["price"], p["name"]
    elif price is None:
        return "Give a price or a product_id."
    opts = plan_options(price)
    emit({"type": "plans", "price": price, "product": name, "product_id": product_id, "options": opts})
    return json.dumps({"price": price, "options": [_plan_brief(o) for o in opts] or "No plan available for this amount."})


@tool
def get_payments() -> str:
    """The user's upcoming installments, amount due in 30 days, outstanding balance, and available spending limit."""
    s = payments_summary()
    emit({"type": "payments", **s})
    return json.dumps({k: s[k] for k in ("due_in_30_days", "total_outstanding", "available_limit", "overdue", "upcoming")})


@tool
def get_order_status(order_ref: Optional[str] = None) -> str:
    """Progress of the user's Tabby orders: installments paid and left, amount left, next and final due dates. order_ref is an order id or product name; omit it for all orders."""
    orders = payments_summary()["orders"]
    if order_ref:
        ref = order_ref.lower()
        orders = [o for o in orders if ref in o["order_id"].lower() or ref in o["product"].lower()] or orders
    for o in orders:
        emit({"type": "order_status", **o})
    return json.dumps([{k: v for k, v in o.items() if k != "installments"} for o in orders])


@tool
def get_payment_methods() -> str:
    """The user's saved cards (default, expiry, active/expired) and their recent payment attempts with failure reasons. Use this to diagnose payment problems."""
    methods = [with_status(m) for m in db.list_payment_methods()]
    by_id = {m["id"]: m for m in methods}
    attempts = [{
        "date": a["created_at"][:10], "amount": a["amount"], "status": a["status"],
        "card": by_id[a["method_id"]]["label"],
        "for": ((a.get("installments") or {}).get("orders") or {}).get("product"),
        "reason": FAILURE_REASONS.get(a["failure_code"]) if a["failure_code"] else None,
    } for a in db.list_payment_attempts()]
    emit({"type": "payment_methods", "methods": methods, "attempts": attempts})
    return json.dumps({"methods": [{k: m[k] for k in ("id", "label", "expiry", "status", "is_default")} for m in methods],
                       "recent_attempts": attempts})


@tool
def check_eligibility(product_id: Optional[str] = None, amount: Optional[float] = None) -> str:
    """Can the user buy this right now? Runs the checkout checks (plan range, limit, overdue payments, card, identity) for a product or amount."""
    name = None
    if product_id:
        p = db.get_product(product_id)
        if not p:
            return f"Unknown product id {product_id}."
        amount, name = p["price"], p["name"]
    if amount is None:
        return "Give a product_id or amount."
    checks = purchase_checks(amount)
    ok = all(c["ok"] for c in checks)
    emit({"type": "eligibility", "product": name, "amount": amount, "eligible": ok, "checks": checks})
    return json.dumps({"eligible": ok, "amount": amount, "checks": checks})


@tool
def search_help_center(query: str) -> str:
    """Search Tabby's help-center articles (payments, cards, plans, limits, refunds, rewards, support). Query in English keywords. Use before answering any policy or how-to question."""
    articles = db.search_help(query)
    emit({"type": "help", "articles": articles})
    return json.dumps(articles) if articles else "No article found."


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

def declined(action: str, title: str, lines: list[tuple[str, str]], confirm_label: str) -> Optional[str]:
    """Pause the graph until the user answers the confirm card.

    Returns None if they confirmed, otherwise why not: they tapped Cancel, or
    they typed a new message instead (which counts as cancelling).
    """
    answer = interrupt({"action": action, "title": title, "lines": lines, "confirm_label": confirm_label}) or {}
    if answer.get("approved"):
        return None
    if answer.get("message"):
        return f"The user did not confirm and wrote instead: {answer['message']!r}. Respond to that."
    return "The user tapped Cancel."


@tool
def start_checkout(product_id: str, plan: Plan) -> str:
    """Buy a product with a Tabby plan. The user must confirm in the app before anything is charged."""
    p = db.get_product(product_id)
    if not p:
        return f"Unknown product id {product_id}."
    opt = next((o for o in plan_options(p["price"]) if o["plan"] == plan), None)
    if not opt:
        return f"{plan} is not available for {p['price']} SAR. Available: {[o['plan'] for o in plan_options(p['price'])]}"
    failed = [c for c in purchase_checks(p["price"]) if not c["ok"]]
    if failed:
        return json.dumps({"status": "blocked", "failed_checks": failed})

    store = p["store_name"]
    lines = [
        ("Store", store),
        ("Price", f"{p['price']:,.0f} SAR"),
        ("Plan", opt["label"]),
        ("Today", f"{opt['per_installment']:,.2f} SAR"),
        ("Then", f"{opt['installments'] - 1} x {opt['per_installment']:,.2f} SAR monthly"),
    ]
    if opt["fee_amount"]:
        lines.append(("Fee", f"{opt['fee_amount']:,.2f} SAR"))
    lines += [("Total", f"{opt['total']:,.2f} SAR"), ("Card", default_card()["label"])]
    if why := declined("checkout", f"Buy {p['name']}", lines, "Confirm purchase"):
        return f"{why} Nothing was charged."

    oid = f"ord_{uuid4().hex[:6]}"
    t = date.today()
    installments = [{"id": f"ins_{oid}_{n + 1}", "order_id": oid, "seq": n + 1, "amount": opt["per_installment"],
                     "due": str(t + timedelta(days=30 * n)), "status": "paid" if n == 0 else "upcoming"}
                    for n in range(opt["installments"])]
    order = {"id": oid, "product": p["name"], "store": store, "total": opt["total"], "plan": plan}
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
    card = default_card()
    if not card or card["status"] != "active":
        return "The default card can't be charged (missing or expired). Ask the user to set another default card first."
    if why := declined("pay_installment", f"Pay {i['amount']:,.2f} SAR now", [
        ("For", f"{o['product']} ({o['store']})"),
        ("Originally due", i["due"]),
        ("Card", card["label"]),
    ], "Pay now"):
        return f"{why} Nothing was paid."
    db.mark_installment_paid(installment_id)
    emit({"type": "receipt", "title": "Payment successful", "order": o})
    return json.dumps({"status": "paid", "remaining_outstanding": payments_summary()["total_outstanding"]})


@tool
def update_home_address(city: str, district: str, street: str, building_number: Optional[str] = None) -> str:
    """Save the user's home address to their profile. Requires confirmation in the app."""
    addr = {"city": city, "district": district, "street": street, "building_number": building_number}
    if why := declined("update_address", "Save home address", [
        ("City", city), ("District", district), ("Street", street), ("Building", building_number or "-"),
    ], "Save"):
        return f"{why} Address not saved."
    db.update_account({"home_address": addr,
                       "profile_completion_pct": min(100, db.get_account()["profile_completion_pct"] + 30)})
    emit({"type": "receipt", "title": "Address saved", "address": addr})
    return "Saved."


@tool
def set_default_card(method_id: str) -> str:
    """Make a saved card the default for all future installments (ids from get_payment_methods). Requires confirmation in the app."""
    m = next((with_status(m) for m in db.list_payment_methods() if m["id"] == method_id), None)
    if not m:
        return f"Unknown card id {method_id}."
    if m["status"] == "expired":
        return f"{m['label']} expired {m['expiry']}; it can't be the default. Ask the user to add a new card in Profile."
    if why := declined("set_default_card", f"Use {m['label']} as default", [
        ("Card", m["label"]), ("Expires", m["expiry"]), ("Applies to", "All upcoming installments"),
    ], "Set as default"):
        return f"{why} Default card unchanged."
    db.set_default_payment_method(method_id)
    emit({"type": "receipt", "title": f"{m['label']} is now your default card"})
    return "Default card updated."


@tool
def create_support_ticket(category: Literal["payments", "cards", "orders", "refunds", "account", "other"], summary: str) -> str:
    """Hand the issue to a human agent when the help center and account checks can't resolve it. Requires confirmation in the app. summary: what the user tried and what went wrong."""
    if why := declined("support_ticket", "Send to a support agent", [
        ("Topic", category.title()), ("Issue", summary), ("Reply", "In the app, usually within 24 hours"),
    ], "Send"):
        return f"{why} No ticket created."
    tid = f"TKT-{uuid4().hex[:6].upper()}"
    db.create_ticket({"id": tid, "category": category, "summary": summary})
    emit({"type": "ticket", "id": tid, "category": category, "summary": summary})
    return json.dumps({"ticket_id": tid, "status": "open", "reply_within": "24 hours"})


READ_TOOLS = [search_products, get_deals, search_stores, compare_products, get_payment_plans,
              get_payments, get_order_status, get_payment_methods, check_eligibility,
              search_help_center, get_account]
UI_TOOLS = [open_screen, share_referral]
ACTION_TOOLS = [start_checkout, pay_installment, update_home_address, set_default_card, create_support_ticket]
ALL_TOOLS = READ_TOOLS + UI_TOOLS + ACTION_TOOLS
