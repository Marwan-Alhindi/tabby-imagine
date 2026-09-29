"""Supabase data access. The only module that talks to the database."""

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

ACCOUNT_ID = "demo"  # single demo user; real auth would supply this


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
    return sb().table("accounts").select("*").eq("id", ACCOUNT_ID).single().execute().data


def update_account(fields: dict) -> None:
    sb().table("accounts").update(fields).eq("id", ACCOUNT_ID).execute()


# ---------------------------------------------------------------- orders & installments

def list_orders() -> list[dict]:
    return (sb().table("orders").select("*, installments(*)").eq("account_id", ACCOUNT_ID)
            .order("created_at").order("seq", foreign_table="installments").execute().data)


def create_order(order: dict, installments: list[dict]) -> None:
    sb().table("orders").insert({**order, "account_id": ACCOUNT_ID}).execute()
    sb().table("installments").insert(installments).execute()


def get_installment(installment_id: str) -> Optional[dict]:
    rows = (sb().table("installments").select("*, orders!inner(id, product, store, account_id)")
            .eq("id", installment_id).eq("orders.account_id", ACCOUNT_ID).execute().data)
    return rows[0] if rows else None


def mark_installment_paid(installment_id: str) -> None:
    sb().table("installments").update({"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}).eq("id", installment_id).execute()


# ---------------------------------------------------------------- payment methods & attempts

def list_payment_methods() -> list[dict]:
    return (sb().table("payment_methods").select("*").eq("account_id", ACCOUNT_ID)
            .order("is_default", desc=True).execute().data)


def set_default_payment_method(method_id: str) -> None:
    sb().table("payment_methods").update({"is_default": False}).eq("account_id", ACCOUNT_ID).execute()
    sb().table("payment_methods").update({"is_default": True}).eq("id", method_id).eq("account_id", ACCOUNT_ID).execute()


def list_payment_attempts(limit: int = 5) -> list[dict]:
    return (sb().table("payment_attempts").select("*, installments(orders(product))").eq("account_id", ACCOUNT_ID)
            .order("created_at", desc=True).limit(limit).execute().data)


# ---------------------------------------------------------------- support

def search_help(query: str, limit: int = 3) -> list[dict]:
    rows = sb().rpc("search_help", {"p_query": query, "p_limit": limit}).execute().data
    return [{k: r[k] for k in ("id", "topic", "title", "body")} for r in rows]


def create_ticket(ticket: dict) -> None:
    sb().table("support_tickets").insert({**ticket, "account_id": ACCOUNT_ID}).execute()


# ---------------------------------------------------------------- chat sessions

def latest_session(max_age_days: int) -> Optional[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    rows = (sb().table("chat_sessions").select("*").eq("account_id", ACCOUNT_ID).gte("updated_at", since)
            .order("updated_at", desc=True).limit(1).execute().data)
    return rows[0] if rows else None


def upsert_session(thread_id: str, language: str, memo: dict) -> None:
    sb().table("chat_sessions").upsert({
        "thread_id": thread_id, "account_id": ACCOUNT_ID, "language": language, "memo": memo,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def list_sessions(max_age_days: int, limit: int = 10) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    rows = (sb().table("chat_sessions").select("*").eq("account_id", ACCOUNT_ID).gte("updated_at", since)
            .order("updated_at", desc=True).limit(limit).execute().data)
    return [r for r in rows if r["memo"].get("turns")]
