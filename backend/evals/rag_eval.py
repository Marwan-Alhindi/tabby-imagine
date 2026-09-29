"""Retrieval eval for the help-center RAG.

    uv run python -m evals.rag_eval

Each case: a user question (English or Saudi-dialect Arabic), the translation
the agent would add, and the help article that answers it. Compares three
retrieval setups on hit@1, hit@5 and MRR.
"""

import re
from dotenv import load_dotenv

load_dotenv()

from app.rag import KBStore, embeddings, reciprocal_rank_fusion  # noqa: E402
from app.db import sb  # noqa: E402

CASES = [  # (question, translation, expected article slug)
    ("I missed my payment, what happens now?", "فاتني القسط وش يصير الحين؟", "what-happens-if-i-miss-a-payment"),
    ("فاتني القسط وش يصير؟", "What happens if I miss a payment?", "what-happens-if-i-miss-a-payment"),
    ("how do I delete my tabby account", "كيف احذف حسابي في تابي", "how-do-i-delete-my-account"),
    ("ابي احذف حسابي", "I want to delete my account", "how-do-i-delete-my-account"),
    ("my order never arrived", "طلبي ما وصل", "what-should-i-do-if-my-order-wasnt-delivered"),
    ("طلبي ما وصلني وش اسوي", "My order wasn't delivered, what do I do?", "what-should-i-do-if-my-order-wasnt-delivered"),
    ("why was my purchase declined?", "ليش انرفضت عملية الشراء؟", "why-was-my-tabby-purchase-not-approved"),
    ("ليش تابي رفض طلبي", "Why was my Tabby purchase not approved?", "why-was-my-tabby-purchase-not-approved"),
    ("are there any fees?", "هل فيه رسوم؟", "are-there-any-fees-to-use-tabby"),
    ("فيه رسوم على تابي؟", "Are there any fees to use Tabby?", "are-there-any-fees-to-use-tabby"),
    ("can I pay off my purchase early", "اقدر اسدد المشتريات بدري؟", "can-i-pay-off-my-purchase-early"),
    ("where is my refund", "وين الاسترداد حقي", "where-is-my-refund"),
    ("وين فلوسي المسترجعة", "Where is my refund?", "where-is-my-refund"),
    ("how do I spend my cashback", "كيف استخدم الكاش باك", "how-can-i-spend-my-cashback"),
    ("someone used my account, report fraud", "احد استخدم حسابي بدون علمي", "how-to-report-fraud"),
    ("my balance is locked", "رصيدي مقفل", "why-is-my-balance-locked"),
    ("how do I contact tabby support", "كيف اتواصل مع تابي", "how-do-i-contact-tabby"),
    ("can I extend my due date", "اقدر أأجل موعد الدفعة؟", "can-i-extend-my-payment-due-date"),
    ("is tabby shariah compliant", "هل تابي متوافق مع الشريعة", "shariah"),
    ("am I eligible to use tabby", "هل اقدر استخدم تابي", "am-i-eligible-to-use-tabby"),
]

store = KBStore(embeddings())
FILTER = {"audience": "consumer"}


def vector_only(q, v, k):
    rows = sb().rpc("kb_hybrid_search", {"query_text": q, "query_embedding": v, "match_count": k,
                                         "filter": FILTER, "full_text_weight": 0}).execute().data
    return [r["metadata"]["url"] for r in rows]


def slug_of(url: str) -> str:
    return re.sub(r"https://tabby\.sa/(en|ar)-SA/", "", url)


def score(ranked_urls, expected):
    ranks = [i for i, u in enumerate(ranked_urls) if expected in slug_of(u)]
    r = ranks[0] + 1 if ranks else None
    return (r == 1, r is not None and r <= 5, 1 / r if r else 0)


def main():
    qs = [c[0] for c in CASES] + [c[1] for c in CASES]
    vecs = embeddings().embed_documents(qs)
    v_q, v_t = vecs[: len(CASES)], vecs[len(CASES):]
    setups = {"vector only": [], "hybrid": [], "hybrid + bilingual fusion": []}
    for (q, t, exp), vq, vt in zip(CASES, v_q, v_t):
        setups["vector only"].append(score(vector_only(q, vq, 5), exp))
        setups["hybrid"].append(score([d.metadata["url"] for d in store.hybrid_search(q, 5, FILTER, vq)], exp))
        fused = reciprocal_rank_fusion([store.hybrid_search(q, 10, FILTER, vq), store.hybrid_search(t, 10, FILTER, vt)])
        setups["hybrid + bilingual fusion"].append(score([d.metadata["url"] for d in fused][:5], exp))
    print(f"{len(CASES)} questions ({sum(bool(re.search('[ء-ي]', c[0])) for c in CASES)} in Arabic)\n")
    print(f"{'setup':28} hit@1  hit@5  MRR")
    for name, s in setups.items():
        n = len(s)
        print(f"{name:28} {sum(x[0] for x in s)/n:.0%}   {sum(x[1] for x in s)/n:.0%}   {sum(x[2] for x in s)/n:.2f}")
    misses = [c[0] for c, s in zip(CASES, setups["hybrid + bilingual fusion"]) if not s[1]]
    if misses:
        print("\nmissed by the full pipeline:", misses)


if __name__ == "__main__":
    main()
