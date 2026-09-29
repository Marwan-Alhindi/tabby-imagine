"""FastAPI server: streams the assistant over SSE and serves app data.

SSE events sent to the client:
  token    {text}                       assistant text as it is generated
  tool     {name, args}                 the assistant started using a tool
  ui       {type, ...}                  a card to render (products, plans, navigate, receipt...)
  confirm  {id, action, title, lines}   an action is waiting for the user's approval
  done     {}                           turn finished
  error    {message}
"""

import json
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from langchain_core.messages import AIMessageChunk, HumanMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sse_starlette.sse import EventSourceResponse  # noqa: E402

from . import data  # noqa: E402
from .agent import graph  # noqa: E402
from .tools import filter_products, payments_summary, _card  # noqa: E402

app = FastAPI(title="Tabby Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    screen: Optional[str] = None  # tab the user was on when they opened the chat


class ResumeRequest(BaseModel):
    thread_id: str
    interrupt_id: str
    approved: bool


def _text(chunk: AIMessageChunk) -> str:
    if isinstance(chunk.content, str):
        return chunk.content
    return "".join(b.get("text", "") for b in chunk.content if isinstance(b, dict) and b.get("type") == "text")


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}


async def _run(graph_input, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    try:
        async for mode, chunk in graph.astream(graph_input, config, stream_mode=["messages", "updates", "custom"]):
            if mode == "messages":
                msg, meta = chunk
                if meta.get("langgraph_node") == "agent" and isinstance(msg, AIMessageChunk):
                    if text := _text(msg):
                        yield _sse("token", {"text": text})
            elif mode == "custom":
                yield _sse("ui", chunk)
            elif mode == "updates":
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        for intr in update:
                            yield _sse("confirm", {"id": intr.id, **intr.value})
                    elif node == "agent":
                        for call in update["messages"][-1].tool_calls:
                            yield _sse("tool", {"name": call["name"], "args": call["args"]})
        yield _sse("done", {})
    except Exception as e:  # surface failures in the chat instead of a dead stream
        yield _sse("error", {"message": str(e)})


@app.post("/api/chat")
async def chat(req: ChatRequest):
    text = req.message if not req.screen else f"[user opened chat from the {req.screen} tab]\n{req.message}"
    return EventSourceResponse(_run({"messages": [HumanMessage(text)]}, req.thread_id))


@app.post("/api/chat/resume")
async def resume(req: ResumeRequest):
    cmd = Command(resume={req.interrupt_id: {"approved": req.approved}})
    return EventSourceResponse(_run(cmd, req.thread_id))


@app.get("/api/products")
def products(
    category: Optional[str] = None,
    query: Optional[str] = None,
    brands: Optional[list[str]] = Query(None),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_storage_gb: Optional[int] = None,
    color: Optional[str] = None,
    store: Optional[str] = None,
    deals_only: bool = False,
    sort_by: str = "relevance",
):
    items = filter_products(query, category, brands, min_price, max_price, min_storage_gb, color, store, deals_only, sort_by)
    return [_card(p) for p in items]


@app.get("/api/payments")
def payments():
    return payments_summary()


@app.get("/api/account")
def account():
    return data.ACCOUNT


@app.get("/api/health")
def health():
    return {"ok": True}
