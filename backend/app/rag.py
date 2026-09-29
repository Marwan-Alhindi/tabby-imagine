"""RAG over Tabby's help center.

Indexing   db/ingest_kb.py loads the crawled articles, splits them, and syncs them
           into `kb_chunks` with LangChain's index() + SQLRecordManager, so
           re-running only embeds what changed and removes what disappeared.
Store      KBStore: a LangChain VectorStore over Supabase pgvector, so index()
           can add and delete by id.
Retrieval  hybrid search per query (full-text + vector, fused in SQL with RRF),
           then RAG-Fusion across the query variants the agent writes (the
           question in the user's language plus a translation), fused again
           with RRF in Python. No extra LLM call: the agent already writes the
           variants as tool arguments.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Iterable, Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from langsmith import traceable

from .db import sb

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, multilingual (Arabic + English)
TABLE = "kb_chunks"
RRF_K = 60
MIN_SIMILARITY = float(os.getenv("KB_MIN_SIMILARITY", "0.30"))  # drop vector-only matches below this cosine similarity
FULL_TEXT_WEIGHT = float(os.getenv("KB_FULL_TEXT_WEIGHT", "0.3"))  # keyword ranking's share in RRF (vector = 1)


@lru_cache
def embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=os.environ["OPENAI_API_KEY"])


class KBStore(VectorStore):
    """Supabase pgvector table with hybrid (full-text + vector) search."""

    def __init__(self, embedding: Embeddings):
        self._embedding = embedding

    @property
    def embeddings(self) -> Embeddings:
        return self._embedding

    def add_texts(self, texts: Iterable[str], metadatas: Optional[list[dict]] = None,
                  *, ids: Optional[list[str]] = None, **kwargs: Any) -> list[str]:
        texts = list(texts)
        metadatas = metadatas or [{} for _ in texts]
        ids = ids or [str(i) for i in range(len(texts))]
        vectors = self._embedding.embed_documents(texts)
        rows = [{"id": i, "content": t, "metadata": m, "embedding": v}
                for i, t, m, v in zip(ids, texts, metadatas, vectors)]
        for start in range(0, len(rows), 100):
            sb().table(TABLE).upsert(rows[start:start + 100]).execute()
        return ids

    def delete(self, ids: Optional[list[str]] = None, **kwargs: Any) -> Optional[bool]:
        for start in range(0, len(ids or []), 100):
            sb().table(TABLE).delete().in_("id", ids[start:start + 100]).execute()
        return True

    def hybrid_search(self, query: str, k: int = 6, filter: Optional[dict] = None,
                      vector: Optional[list[float]] = None) -> list[Document]:
        vector = vector or self._embedding.embed_query(query)
        rows = sb().rpc("kb_hybrid_search", {
            "query_text": query, "query_embedding": vector, "match_count": k, "filter": filter or {},
            "full_text_weight": FULL_TEXT_WEIGHT,
        }).execute().data
        return [Document(id=r["id"], page_content=r["content"],
                         metadata={**r["metadata"], "similarity": round(r["similarity"], 3),
                                   "fts_rank": r["fts_rank"], "vec_rank": r["vec_rank"]})
                for r in rows if r["fts_rank"] or r["similarity"] >= MIN_SIMILARITY]

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        return self.hybrid_search(query, k, kwargs.get("filter"))

    @classmethod
    def from_texts(cls, texts: list[str], embedding: Embeddings, metadatas: Optional[list[dict]] = None, **kwargs: Any):
        store = cls(embedding)
        store.add_texts(texts, metadatas, ids=kwargs.get("ids"))
        return store


def reciprocal_rank_fusion(results: list[list[Document]], k: int = RRF_K) -> list[Document]:
    """Fuse several ranked lists into one: score = sum of 1 / (rank + k)."""
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for ranked in results:
        for rank, doc in enumerate(ranked):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (rank + k)
            docs.setdefault(doc.id, doc)
    return [docs[i] for i in sorted(scores, key=scores.get, reverse=True)]


class HelpCenterRetriever(BaseRetriever):
    """RAG-Fusion retriever: hybrid search for each query variant, then RRF."""

    store: Any
    k: int = 5
    audience: Optional[str] = "consumer"

    @traceable(run_type="retriever", name="help_center_rag_fusion")
    def retrieve(self, queries: list[str]) -> list[Document]:
        queries = [q.strip() for q in queries if q and q.strip()][:4]
        vectors = self.store.embeddings.embed_documents(queries)  # one batched embeddings call
        flt = {"audience": self.audience} if self.audience else {}
        with ThreadPoolExecutor(len(queries)) as pool:
            ranked = list(pool.map(lambda qv: self.store.hybrid_search(qv[0], self.k * 2, flt, qv[1]),
                                   zip(queries, vectors)))
        return reciprocal_rank_fusion(ranked)[: self.k]

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        return self.retrieve([query])


@lru_cache
def retriever(audience: Optional[str] = "consumer") -> HelpCenterRetriever:
    return HelpCenterRetriever(store=KBStore(embeddings()), audience=audience)
