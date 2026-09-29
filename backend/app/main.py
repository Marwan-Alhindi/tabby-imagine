"""FastAPI server: streams the assistant over SSE and serves app data.

SSE events sent to the client:
  token    {text}                       assistant text as it is generated
  tool     {name, args}                 the assistant started using a tool
  ui       {type, ...}                  a card to render (products, plans, navigate, receipt...)
  confirm  {id, action, title, lines}   an action is waiting for the user's approval
  done     {}                           turn finished
  error    {message}

Memory: the full conversation is checkpointed in Supabase Postgres by LangGraph
(Tabby's record). After each turn a small memo is saved to `chat_sessions`;
that memo, not the transcript, is what the user sees when they come back.
"""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from langchain_core.messages import AIMessageChunk, HumanMessage  # noqa: E402
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402
from psycopg_pool import AsyncConnectionPool  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sse_starlette.sse import EventSourceResponse  # noqa: E402

from . import db  # noqa: E402
from .agent import build_graph  # noqa: E402
from .memory import build_memo  # noqa: E402
from .tools import payments_summary, _card  # noqa: E402

SESSION_TTL_DAYS = 7  # how long the user is offered to pick up where they left off
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))

Language = Literal["ar", "en"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncConnectionPool(
        os.environ["SUPABASE_DB_URL"], max_size=5, open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    ) as pool:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()  # creates LangGraph's checkpoint tables if missing
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="Tabby Assistant", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def visitor(x_visitor_id: Optional[str] = Header(None)) -> str:
    """Scope the request to the visitor's own demo account (created on first visit)."""
    aid = db.visitor_account(x_visitor_id)
    db.use_account(aid)
    await asyncio.to_thread(db.ensure_account, aid)
    return aid


# Public demo: cap chat turns so one visitor can't run up the model bill.
LIMITS = {"visitor": (30, 3600), "ip": (80, 3600)}  # max turns per window (seconds)
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, kind: str) -> None:
    limit, window = LIMITS[kind]
    q, now = _hits[f"{kind}:{key}"], time.monotonic()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "You've reached the demo's message limit for now. Please try again in a while.")
    q.append(now)


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    language: Language = "en"
    screen: Optional[str] = None  # tab the user was on when they opened the chat


class ResumeRequest(BaseModel):
    thread_id: str
    interrupt_id: str
    approved: bool


class LanguageRequest(BaseModel):
    language: Language


def _text(chunk: AIMessageChunk) -> str:
    if isinstance(chunk.content, str):
        return chunk.content
    return "".join(b.get("text", "") for b in chunk.content if isinstance(b, dict) and b.get("type") == "text")


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def _save_memo(graph, thread_id: str) -> None:
    state = await graph.aget_state(_config(thread_id))
    memo = await asyncio.to_thread(build_memo, state.values.get("messages", []))
    await asyncio.to_thread(db.upsert_session, thread_id, state.values.get("language") or "en", memo)


async def _run(graph, graph_input, thread_id: str, aid: str):
    db.use_account(aid)  # the stream runs in its own task; re-scope it to the visitor
    try:
        async for mode, chunk in graph.astream(graph_input, _config(thread_id), stream_mode=["messages", "updates", "custom"]):
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
        await _save_memo(graph, thread_id)
        yield _sse("done", {})
    except Exception as e:  # surface failures in the chat instead of a dead stream
        yield _sse("error", {"message": str(e)})


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request, aid: str = Depends(visitor)):
    rate_limit(aid, "visitor")
    rate_limit(request.headers.get("x-forwarded-for", request.client.host).split(",")[0], "ip")
    graph = app.state.graph
    pending = (await graph.aget_state(_config(req.thread_id))).interrupts
    if pending:
        # The user typed instead of answering the confirm card: treat it as Cancel
        # and hand their message to the paused tool so the agent can respond to it.
        graph_input = Command(resume={i.id: {"approved": False, "message": req.message} for i in pending})
    else:
        text = req.message if not req.screen else f"[user opened chat from the {req.screen} tab]\n{req.message}"
        graph_input = {"messages": [HumanMessage(text)], "language": req.language}
    return EventSourceResponse(_run(graph, graph_input, req.thread_id, aid))


@app.post("/api/chat/resume")
async def resume(req: ResumeRequest, aid: str = Depends(visitor)):
    cmd = Command(resume={req.interrupt_id: {"approved": req.approved}})
    return EventSourceResponse(_run(app.state.graph, cmd, req.thread_id, aid))


@app.get("/api/session")
async def session(aid: str = Depends(visitor)):
    """What the assistant tab needs on open: the saved language and, if recent, the last session's memo."""
    account = await asyncio.to_thread(db.get_account)
    s = await asyncio.to_thread(db.latest_session, SESSION_TTL_DAYS)
    if s and s["memo"].get("turns"):
        state = await app.state.graph.aget_state(_config(s["thread_id"]))
        s["pending"] = [{"id": i.id, **i.value} for i in state.interrupts]
    else:
        s = None
    return {"language": account["language"], "session": s}


@app.get("/api/sessions")
async def sessions(aid: str = Depends(visitor)):
    """Recent sessions for the history sheet: memos only, never transcripts."""
    rows = await asyncio.to_thread(db.list_sessions, SESSION_TTL_DAYS)
    for s in rows:
        s["pending"] = [{"id": i.id, **i.value} for i in (await app.state.graph.aget_state(_config(s["thread_id"]))).interrupts]
    return rows


@app.post("/api/language")
def set_language(req: LanguageRequest, aid: str = Depends(visitor)):
    db.update_account({"language": req.language})
    return {"language": req.language}


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
    sort: str = "relevance",
):
    res = db.search_products(query=query, category=category, brands=brands, min_price=min_price, max_price=max_price,
                             min_storage_gb=min_storage_gb, color=color, store=store, deals_only=deals_only, sort=sort)
    return [_card(p) for p in res["items"]]


@app.get("/api/payments")
def payments(aid: str = Depends(visitor)):
    return payments_summary()


@app.get("/api/account")
def account(aid: str = Depends(visitor)):
    return db.get_account()


@app.get("/api/health")
def health():
    return {"ok": True}


# The built React app, served from the same origin as the API (one link to share).
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
