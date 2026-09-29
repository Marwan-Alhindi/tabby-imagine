"""Load Tabby's help-center articles into the RAG store.

    uv run python -m db.ingest_kb

Idempotent: LangChain's index() with a SQLRecordManager skips unchanged
chunks, re-embeds changed ones, and deletes chunks whose article is gone
(cleanup="full").
"""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langchain_classic.indexes import SQLRecordManager
from langchain_core.documents import Document
from langchain_core.indexing import index
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

from app.rag import KBStore, embeddings  # noqa: E402

KB_FILE = Path(__file__).resolve().parents[1] / "app" / "kb" / "tabby_help.json"

# FAQ answers are short: most articles stay whole. Long pages split on
# paragraphs, then sentences (Arabic and Latin punctuation), then words.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", "؟ ", "? ", "! ", "، ", "؛ ", ", ", " ", ""],
)


def load_documents() -> list[Document]:
    articles = json.loads(KB_FILE.read_text())
    docs = []
    for a in articles:
        base = {k: a.get(k) for k in ("url", "title", "language", "audience", "category")}
        base["source"] = f"{a['url']}#{a['id']}"
        for n, chunk in enumerate(splitter.split_text(a["body"])):
            # Contextual header: every chunk carries its article title, so a
            # chunk from the middle of an answer still says what it's about.
            docs.append(Document(page_content=f"{a['title']}\n\n{chunk}", metadata={**base, "chunk": n}))
    return docs


def main():
    db_url = os.environ["SUPABASE_DB_URL"]
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute((Path(__file__).parent / "kb_schema.sql").read_text())

    record_manager = SQLRecordManager("tabby_help_center", db_url=db_url.replace("postgresql://", "postgresql+psycopg://", 1))
    record_manager.create_schema()

    docs = load_documents()
    result = index(docs, record_manager, KBStore(embeddings()), cleanup="full", source_id_key="source", batch_size=64, key_encoder="sha256")
    print(f"{len(docs)} chunks from {KB_FILE.name}: {result}")

    with psycopg.connect(db_url, autocommit=True) as conn:  # lock down the record manager's new table too
        conn.execute("alter table if exists upsertion_record enable row level security")


if __name__ == "__main__":
    main()
