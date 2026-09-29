"""Supabase data access. The only module that talks to the database."""

import os
import re
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

TEMPLATE_ACCOUNT = "demo"  # seeded account every visitor gets a private copy of

# The account the current request acts for. Set per request from the visitor id;
# real auth would supply it. Context vars follow LangGraph into its worker threads.
_account: ContextVar[str] = ContextVar("account", default=TEMPLATE_ACCOUNT)


def account_id() -> str:
    return _account.get()


def visitor_account(visitor_id: Optional[str]) -> str:
    """Each browser gets its own copy of the demo account, keyed by a random id it stores."""
    if not visitor_id or not re.fullmatch(r"[A-Za-z0-9-]{8,64}", visitor_id):
        return TEMPLATE_ACCOUNT
    return "v_" + visitor_id.replace("-", "")[:16]


def use_account(aid: str) -> None:
    _account.set(aid)


def ensure_account(aid: str) -> None:
    """Clone the template account (cards, orders, installments, payment history) for a new visitor."""
    if aid == TEMPLATE_ACCOUNT or sb().table("accounts").select("id").eq("id", aid).execute().data:
        return
    sfx = aid[-6:]
    rid = lambda x: f"{x}_{sfx}" if x else x  # noqa: E731
    t = TEMPLATE_ACCOUNT

    acct = sb().table("accounts").select("*").eq("id", t).single().execute().data
    sb().table("accounts").upsert({**acct, "id": aid, "language": None}, ignore_duplicates=True).execute()
    methods = sb().table("payment_methods").select("*").eq("account_id", t).execute().data
    sb().table("payment_methods").upsert([{**m, "id": rid(m["id"]), "account_id": aid} for m in methods], ignore_duplicates=True).execute()
    orders = sb().table("orders").select("*, installments(*)").eq("account_id", t).execute().data
    for o in orders:
        ins = o.pop("installments")
        o.pop("created_at", None)
        sb().table("orders").upsert({**o, "id": rid(o["id"]), "account_id": aid}, ignore_duplicates=True).execute()
        sb().table("installments").upsert(
            [{**i, "id": rid(i["id"]), "order_id": rid(i["order_id"])} for i in ins], ignore_duplicates=True).execute()
    attempts = sb().table("payment_attempts").select("*").eq("account_id", t).execute().data
    sb().table("payment_attempts").upsert([{**a, "id": rid(a["id"]), "account_id": aid, "method_id": rid(a["method_id"]),
                                            "installment_id": rid(a["installment_id"])} for a in attempts],
                                          ignore_duplicates=True).execute()


@lru_cache
def sb() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ---------------------------------------------------------------- catalog

def search_products(limit: int = 50, **filters) -> dict:
    """Runs the `search_products` SQL function. Returns {total, items}."""
    params = {f"p_{k}": v for k, v in filters.items() if v is not None}
    return sb().rpc("search_products", {**params, "p_limit": limit}).execute().data


def get_product(product_id: str) -> Optional[dict]:
    rows = sb().table("product_cards").select("*").eq("id", product_id).execute().data
    return rows[0] if rows else None


def get_products(ids: list[str]) -> list[dict]:
    rows = sb().table("product_cards").select("*").in_("id", ids).execute().data
    return sorted(rows, key=lambda p: ids.index(p["id"]))


def list_stores(query: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    q = sb().table("stores").select("*").order("cashback_pct", desc=True)
    if category:
        q = q.contains("categories", [category])
    if query:
        q = q.ilike("name", f"%{query}%")
    return q.execute().data


# ---------------------------------------------------------------- account

def get_account() -> dict:
    return sb().table("accounts").select("*").eq("id", account_id()).single().execute().data


def update_account(fields: dict) -> None:
    sb().table("accounts").update(fields).eq("id", account_id()).execute()


# ---------------------------------------------------------------- orders & installments

def list_orders() -> list[dict]:
    return (sb().table("orders").select("*, installments(*)").eq("account_id", account_id())
            .order("created_at").order("seq", foreign_table="installments").execute().data)


def create_order(order: dict, installments: list[dict]) -> None:
    sb().table("orders").insert({**order, "account_id": account_id()}).execute()
    sb().table("installments").insert(installments).execute()


def get_installment(installment_id: str) -> Optional[dict]:
    rows = (sb().table("installments").select("*, orders!inner(id, product, store, account_id)")
            .eq("id", installment_id).eq("orders.account_id", account_id()).execute().data)
    return rows[0] if rows else None


def mark_installment_paid(installment_id: str) -> None:
    sb().table("installments").update({"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}).eq("id", installment_id).execute()


# ---------------------------------------------------------------- payment methods & attempts

def list_payment_methods() -> list[dict]:
    return (sb().table("payment_methods").select("*").eq("account_id", account_id())
            .order("is_default", desc=True).execute().data)


def set_default_payment_method(method_id: str) -> None:
    sb().table("payment_methods").update({"is_default": False}).eq("account_id", account_id()).execute()
    sb().table("payment_methods").update({"is_default": True}).eq("id", method_id).eq("account_id", account_id()).execute()


def list_payment_attempts(limit: int = 5) -> list[dict]:
    return (sb().table("payment_attempts").select("*, installments(orders(product))").eq("account_id", account_id())
            .order("created_at", desc=True).limit(limit).execute().data)


# ---------------------------------------------------------------- support

def create_ticket(ticket: dict) -> None:
    sb().table("support_tickets").insert({**ticket, "account_id": account_id()}).execute()


# ---------------------------------------------------------------- chat sessions

def latest_session(max_age_days: int) -> Optional[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    rows = (sb().table("chat_sessions").select("*").eq("account_id", account_id()).gte("updated_at", since)
            .order("updated_at", desc=True).limit(1).execute().data)
    return rows[0] if rows else None


def upsert_session(thread_id: str, language: str, memo: dict) -> None:
    sb().table("chat_sessions").upsert({
        "thread_id": thread_id, "account_id": account_id(), "language": language, "memo": memo,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def list_sessions(max_age_days: int, limit: int = 10) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    rows = (sb().table("chat_sessions").select("*").eq("account_id", account_id()).gte("updated_at", since)
            .order("updated_at", desc=True).limit(limit).execute().data)
    return [r for r in rows if r["memo"].get("turns")]
