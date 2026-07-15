"""Hybrid retrieval over the unified `documents` table.

Uses the existing Postgres RPC `match_hybridsearch_full(query_text, query_embedding,
match_count, filter_doc_type)` — reciprocal-rank fusion of pgvector cosine search and
full-text search. Returns id, content, doc_type, source_document, score.

`search_documents(...)` is the backend for the Phase-2 `vector_search` agent tool.
"""
import re
from typing import Optional

from app.database import get_supabase
from app.rag.embed import embed_query

# doc_type values allowed in the KB (see docs/DATA_MODEL.md).
DOC_TYPES = {"catalog", "masterprice", "policy", "technical", "website"}


def _to_tsquery(text: str) -> str:
    """Turn free text into a safe `to_tsquery('simple', ...)` string.

    The RPC calls `to_tsquery('simple', query_text)`, which errors on raw punctuation/spaces.
    We extract word tokens and OR them together (recall-friendly; the vector side handles
    precision). Returns '' when there are no usable tokens (the RPC's FTS branch then
    contributes nothing and vector search still returns results).
    """
    tokens = re.findall(r"\w+", text or "", flags=re.UNICODE)
    return " | ".join(tokens)


def search_documents(query: str, doc_type: Optional[str] = None, top_k: int = 5) -> list[dict]:
    """Retrieve the most relevant document chunks for `query`.

    Args:
        query: natural-language search text.
        doc_type: optional filter to one of DOC_TYPES; None searches all.
        top_k: number of results to return.

    Returns a list of dicts: {content, doc_type, source_document, score}.
    """
    supabase = get_supabase()
    if supabase is None:
        raise RuntimeError("Supabase not configured — check SUPABASE_URL / key")

    if doc_type is not None and doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type must be one of {sorted(DOC_TYPES)} or None, got {doc_type!r}")

    embedding = embed_query(query)

    resp = supabase.rpc(
        "match_hybridsearch_full",
        {
            "query_text": _to_tsquery(query),
            "query_embedding": embedding,
            "match_count": top_k,
            "filter_doc_type": doc_type,
        },
    ).execute()

    rows = resp.data or []
    return [
        {
            "content": r.get("content"),
            "doc_type": r.get("doc_type"),
            "source_document": r.get("source_document"),
            "score": r.get("score"),
        }
        for r in rows
    ]
