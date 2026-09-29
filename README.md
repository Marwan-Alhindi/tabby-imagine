# Tabby Assistant (Tabby Imagine submission)

An AI assistant tab in the Tabby app that can search every part of the app and act in it, in Arabic or English.

## Run locally
```
cd backend && uv run uvicorn app.main:app --port 8000
cd frontend && npx vite            # http://localhost:5173
```
`backend/.env` needs `ANTHROPIC_API_KEY`; LangSmith tracing uses `LANGSMITH_*` (project `tabby-imagine`).

## Design
- `backend/app/agent.py`: LangGraph loop `agent -> tools -> agent`, checkpointed per thread.
- `backend/app/tools.py`: read tools (search, deals, stores, compare, plans, payments, account), UI tools (open a tab with filters), action tools (checkout, pay installment, save address).
- Action tools pause the graph with `interrupt()`; only the user's tap on Confirm (a separate `/api/chat/resume` call) resumes them. The model can't approve its own actions.
- Tools stream structured UI events (cards) separately from the text they return to the model.
- `backend/app/data.py`: mock catalog/account standing in for Tabby services.

## Visualize the graph (LangGraph Studio)
```
cd backend && uv run langgraph dev
```
Opens https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024 (uses `LANGSMITH_API_KEY`).

## Language and memory
- The assistant asks for Arabic or English on first open; saved in `accounts.language`, switchable from the chat header. Replies, UI text and RTL follow it.
- Tabby's record: every conversation is checkpointed in Supabase Postgres (LangGraph `AsyncPostgresSaver`) and traced in LangSmith.
- The user's view: no transcript. Returning within 7 days shows a "Welcome back" card built from a structured memo (`chat_sessions.memo`: plans viewed, last search, checkout status, tickets). Continue resumes the thread with full context, including a purchase left waiting for confirmation.

## Deploy (Render)
One Docker image (`Dockerfile`) builds the React app and serves it with the API. `render.yaml` defines the service; set the secret env vars in Render. Each browser gets its own copy of the seeded demo account, and chat is rate-limited per visitor. Reset demo data with `cd backend && uv run python -m db.seed`.

## Help-center RAG
- Source: 300 articles (Arabic + English, consumer + business) scraped from tabby.sa's help centers and FAQ pages into `backend/app/kb/tabby_help.json`.
- Indexing: `uv run python -m db.ingest_kb`. `RecursiveCharacterTextSplitter` (Arabic-aware separators, title header on every chunk) → OpenAI `text-embedding-3-small` → Supabase pgvector (`kb_chunks`, HNSW). LangChain `index()` + `SQLRecordManager` makes it incremental: unchanged chunks are skipped, changed ones re-embedded, removed ones deleted.
- Retrieval (`app/rag.py`): hybrid search in SQL (full-text + vector, RRF) per query, then RAG-Fusion across the variants the agent writes (question + its translation), fused again with RRF. Traced in LangSmith.
- Eval: `uv run python -m evals.rag_eval` (20 English and Saudi-dialect questions):

| setup | hit@1 | hit@5 | MRR |
|---|---|---|---|
| vector only | 60% | 95% | 0.75 |
| hybrid (single query) | 65% | 80% | 0.72 |
| hybrid + bilingual fusion (used) | 70% | 100% | 0.81 |
