"""The user-facing session memo.

Tabby keeps the full conversation (LangGraph checkpoints in Postgres, traces in
LangSmith). The user only gets this memo back when they return: a few
structured facts derived from tool calls, never free text from the chat.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from . import db


def _parse(content) -> object:
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


def build_memo(messages: list) -> dict:
    results = {m.tool_call_id: _parse(m.content) for m in messages if isinstance(m, ToolMessage)}
    memo: dict = {"turns": sum(isinstance(m, HumanMessage) for m in messages)}
    plan_ids: list[str] = []
    topics: set[str] = set()

    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        for call in m.tool_calls:
            name, args, result = call["name"], call["args"], results.get(call["id"])
            if name == "search_products":
                memo["last_search"] = {k: v for k, v in args.items() if v not in (None, False, "relevance") and k != "limit"}
            elif name == "get_payment_plans" and args.get("product_id"):
                plan_ids = [i for i in plan_ids if i != args["product_id"]] + [args["product_id"]]
            elif name == "start_checkout":
                if result is None:
                    status = "pending"          # interrupted, waiting for the user's confirmation
                elif isinstance(result, dict):
                    status = result.get("status", "unknown")
                else:
                    text = str(result).lower()
                    status = "cancelled" if "cancel" in text or "did not confirm" in text else "failed"
                memo["checkout"] = {"product_id": args.get("product_id"), "plan": args.get("plan"), "status": status}
            elif name == "create_support_ticket" and isinstance(result, dict):
                memo["ticket"] = result.get("ticket_id")
            elif name == "get_payment_methods":
                topics.add("cards")
            elif name in ("get_order_status", "get_payments"):
                topics.add("payments")
            elif name == "check_eligibility":
                topics.add("eligibility")

    ids = plan_ids[-3:] + ([memo["checkout"]["product_id"]] if "checkout" in memo else [])
    names = {p["id"]: {"name": p["name"], "price": p["price"]} for p in db.get_products(list(dict.fromkeys(ids)))} if ids else {}
    if plan_ids:
        memo["viewed_plans"] = [{"product_id": i, **names[i]} for i in reversed(plan_ids[-3:]) if i in names]
    if "checkout" in memo and memo["checkout"]["product_id"] in names:
        memo["checkout"]["name"] = names[memo["checkout"]["product_id"]]["name"]
    if topics:
        memo["topics"] = sorted(topics)
    return memo
