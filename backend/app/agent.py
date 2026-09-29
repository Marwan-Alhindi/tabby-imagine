"""The LangGraph assistant.

    START -> agent -> (tool calls?) -> tools -> agent -> ... -> END

`agent` is Claude with the tool list bound. `tools` runs them; action tools may
pause the whole graph with `interrupt()` until the user confirms in the app.
State is checkpointed per thread in Postgres, so a paused conversation resumes
exactly where it stopped, even days later.
"""

import logging
import os
from datetime import date
from functools import lru_cache
from typing import Literal, get_args

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from . import db
from .tools import ALL_TOOLS, LONG_PLAN_MAX, LONG_PLAN_MIN, SPLIT_IN_4_MAX, Category


LANGUAGE_RULE = {
    "ar": "Always reply in Arabic, in a natural Saudi tone, even if the user writes in English. Keep product names as they are.",
    "en": "Always reply in English, even if the user writes in Arabic.",
}


class State(MessagesState):
    language: Literal["ar", "en"]  # chosen by the user when they open the assistant


@lru_cache
def system_prompt(today: date, language: str) -> str:
    return f"""You are Tabby Assistant, the in-app helper of Tabby, the Saudi buy-now-pay-later app.
You live in a tab of the app and can search it and act in it on the user's behalf.

What you can do
- Find products, deals and stores, and filter them exactly as the user describes (brand, budget, storage, color, store...). Results appear as cards under your message, so do not repeat every detail in text: summarize, highlight the best fit, and ask one short follow-up if it helps narrow down.
- Explain Tabby plans: split in 4 interest-free (up to {SPLIT_IN_4_MAX:,} SAR), or monthly over 6 or 12 months ({LONG_PLAN_MIN:,} to {LONG_PLAN_MAX:,} SAR). Use get_payment_plans for exact numbers.
- Show the user's payments, how far along each order is (paid, left, months to go), limit, cashback and referral reward.
- Customer support: solve problems like a failed card payment, a declined order, or "can I buy this?".
- Take actions: open a screen with filters, buy with a plan, pay an installment early, change the default card, save a home address, share the invite link, open a support ticket.

Support workflow
- Diagnose from the user's own data first: get_payment_methods for card or payment failures (expiry, failed attempts and their reasons), check_eligibility for "can I buy" or declined orders, get_order_status for "how much / how many months left".
- Use search_help_center for policies and how-tos (Tabby's official help center). Pass the question as asked plus its translation into the other language. Answer only from the returned content, never from memory, and name the article you used. If nothing returned answers it, say so and offer a support ticket.
- Tell the user the cause in one line, then the fix, and offer the action that fixes it (e.g. set another card as default).
- If you can't resolve it, offer a support ticket with a clear summary.

Plans and checkout
- When the user asks about plans for a product, call get_payment_plans with its product_id. The card shows every plan with its total and dates and a pay button, so keep your text to a one-line recommendation.
- If the user picks a plan, call start_checkout. If checkout is blocked, explain the failed check and how to fix it.

Rules
- Only state products, prices and account facts that came from a tool result in this conversation. Never invent them.
- Results are capped. Only call something the cheapest, best rated, etc. if you searched with that sort; otherwise search again with the right sort.
- Budgets said per month mean the monthly installment, not the price. Convert before searching.
- Categories: {", ".join(get_args(Category))}. Translate Arabic or colloquial requests into English tool filters (جوال = mobiles, ايفون = Apple iPhone).
- Purchases, payments and profile changes go through their action tool; the app then asks the user to confirm. Never claim an action happened unless the tool result says so. If the user cancels, acknowledge it briefly.
- Call tools directly, without writing anything before them. Speak only once you have results.
- If something is outside Tabby shopping and payments, say so in one line.
- {LANGUAGE_RULE[language]} Keep replies short: a few lines, no headings. Prices in SAR.
Today is {today:%A %d %B %Y}. The user's name is {db.get_account()["name"]}."""

MODEL = os.getenv("TABBY_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("TABBY_EFFORT", "low")  # chat: keep it snappy

FALLBACK_MODEL = os.getenv("TABBY_FALLBACK_MODEL", "qwen3:8b")   # open model served by Ollama
SIMULATE_OUTAGE = os.getenv("TABBY_SIMULATE_OUTAGE") == "1"      # demo: force the fallback path

log = logging.getLogger("tabby.agent")

primary = ChatAnthropic(
    model=MODEL,
    max_tokens=4096,
    output_config={"effort": EFFORT},
    default_request_timeout=30,
    max_retries=1,
).bind_tools(ALL_TOOLS)

# Open-weights backup, run locally: keeps the assistant up if the Anthropic API is
# unreachable, rate-limited or erroring. Same tools and prompt.
fallback = FALLBACK_MODEL and ChatOllama(
    model=FALLBACK_MODEL,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    reasoning=False,
    num_ctx=16384,
    temperature=0,
).bind_tools(ALL_TOOLS)


def _plain(messages: list) -> list:
    """Strip provider-specific blocks (e.g. Claude thinking) so the open model gets text + tool calls."""
    out = []
    for m in messages:
        if isinstance(m, AIMessage) and isinstance(m.content, list):
            text = "".join(b.get("text", "") for b in m.content if isinstance(b, dict) and b.get("type") == "text")
            m = AIMessage(content=text, tool_calls=m.tool_calls, id=m.id)
        out.append(m)
    return out


def agent(state: State):
    # System prompt is prepended per call (not stored), so history stays append-only.
    prompt = system_prompt(date.today(), state.get("language") or "en")
    messages = [SystemMessage(prompt), *state["messages"]]
    try:
        if SIMULATE_OUTAGE:
            raise RuntimeError("simulated outage")
        return {"messages": [primary.invoke(messages)]}
    except Exception as e:  # any provider failure: timeout, 5xx, 429, auth, network
        if not FALLBACK_MODEL:
            raise
        log.warning("primary model failed (%s); falling back to %s", e, FALLBACK_MODEL)
        try:
            get_stream_writer()({"type": "model_fallback", "model": FALLBACK_MODEL})
        except RuntimeError:
            pass
        return {"messages": [fallback.invoke(_plain(messages))]}


def build_graph(checkpointer=None):
    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(ALL_TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer)


# The FastAPI server builds its own graph with the Postgres checkpointer (see main.py).
studio_graph = build_graph()  # LangGraph Studio supplies its own persistence
