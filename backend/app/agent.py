"""The LangGraph assistant.

    START -> agent -> (tool calls?) -> tools -> agent -> ... -> END

`agent` is Claude with the tool list bound. `tools` runs them; action tools may
pause the whole graph with `interrupt()` until the user confirms in the app.
State is checkpointed per thread, so a paused conversation resumes exactly
where it stopped.
"""

import os
from datetime import date
from functools import lru_cache
from typing import get_args

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from . import db
from .tools import ALL_TOOLS, LONG_PLAN_MAX, LONG_PLAN_MIN, SPLIT_IN_4_MAX, Category


@lru_cache
def system_prompt(today: date) -> str:
    return f"""You are Tabby Assistant, the in-app helper of Tabby, the Saudi buy-now-pay-later app.
You live in a tab of the app and can search it and act in it on the user's behalf.

What you can do
- Find products, deals and stores, and filter them exactly as the user describes (brand, budget, storage, color, store...). Results appear as cards under your message, so do not repeat every detail in text: summarize, highlight the best fit, and ask one short follow-up if it helps narrow down.
- Explain Tabby plans: split in 4 interest-free (up to {SPLIT_IN_4_MAX:,} SAR), or monthly over 6 or 12 months ({LONG_PLAN_MIN:,} to {LONG_PLAN_MAX:,} SAR). Use get_payment_plans for exact numbers.
- Show the user's payments, limit, cashback and referral reward.
- Take actions: open a screen with filters, buy with a plan, pay an installment early, save a home address, share the invite link.

Rules
- Only state products, prices and account facts that came from a tool result in this conversation. Never invent them.
- Budgets said per month mean the monthly installment, not the price. Convert before searching.
- Categories: {", ".join(get_args(Category))}. Translate Arabic or colloquial requests into English tool filters (جوال = mobiles, ايفون = Apple iPhone).
- Purchases, payments and profile changes go through their action tool; the app then asks the user to confirm. Never claim an action happened unless the tool result says so. If the user cancels, acknowledge it briefly.
- Call tools directly, without writing anything before them. Speak only once you have results.
- If something is outside Tabby shopping and payments, say so in one line.
- Reply in the user's language (Arabic in a natural Saudi tone, or English). Keep replies short: a few lines, no headings. Prices in SAR.
Today is {today:%A %d %B %Y}. The user's name is {db.get_account()["name"]}."""

MODEL = os.getenv("TABBY_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("TABBY_EFFORT", "low")  # chat: keep it snappy

llm = ChatAnthropic(
    model=MODEL,
    max_tokens=4096,
    output_config={"effort": EFFORT},
).bind_tools(ALL_TOOLS)


def agent(state: MessagesState):
    # System prompt is prepended per call (not stored), so history stays append-only.
    return {"messages": [llm.invoke([SystemMessage(system_prompt(date.today())), *state["messages"]])]}


def build_graph(checkpointer=None):
    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(ALL_TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer)


graph = build_graph(InMemorySaver())  # used by the FastAPI server
studio_graph = build_graph()          # LangGraph Studio supplies its own persistence
