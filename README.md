# Tabby Assistant (Tabby Imagine submission)

An AI assistant tab in the Tabby app that can search every part of the app and act in it, in Arabic or English.

## Run
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
