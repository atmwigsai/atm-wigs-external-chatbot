"""Phase 1 smoke test for the retrieval layer (read-only, no chat-path changes).

Run from the frontend_ui directory:  python scripts/test_retrieval.py

It (1) confirms the query embedding dimension, (2) checks embedding-model compatibility by
embedding a stored chunk and verifying pure-vector search returns that same chunk with high
similarity, then (3) prints hybrid-search results for a few sample questions so you can eyeball
retrieval quality. Requires OPENAI_API_KEY (+ Supabase keys) in the environment or .env.
"""
import os
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # frontend_ui/
load_dotenv(os.path.join(ROOT, ".env"))
sys.path.insert(0, ROOT)

from app.database import get_supabase, get_openai            # noqa: E402
from app.rag.embed import embed_query, EMBEDDING_MODEL, EMBEDDING_DIM  # noqa: E402
from app.rag.search import search_documents                 # noqa: E402

SAMPLE_QUERIES = [
    ("What colors does the Shiraz style come in?", None),
    ("difference between cap M2 and M3", "technical"),
    ("what is double drawn hair", "technical"),
    ("refund policy", "policy"),
    ("do you ship to Germany", None),
]


def main():
    if get_openai() is None:
        print("ERROR: OPENAI_API_KEY not set. Add it to frontend_ui/.env and retry.")
        sys.exit(1)
    supabase = get_supabase()
    if supabase is None:
        print("ERROR: Supabase not configured (SUPABASE_URL / key).")
        sys.exit(1)

    # (1) Embedding dimension
    dim = len(embed_query("hello world"))
    ok = "OK" if dim == EMBEDDING_DIM else "MISMATCH!"
    print(f"[1] Embedding model={EMBEDDING_MODEL}  dim={dim} (expected {EMBEDDING_DIM}) -> {ok}")

    # (2) Embedding-model compatibility: embed a stored chunk's exact content and confirm
    #     pure-vector search returns that same row with very high similarity (~>0.9).
    sample = (
        supabase.table("documents")
        .select("id,content,doc_type,source_document")
        .limit(1)
        .execute()
        .data
    )
    if sample:
        s = sample[0]
        emb = embed_query(s["content"])
        vec = supabase.rpc(
            "match_hybridsearch", {"query_embedding": emb, "match_count": 3}
        ).execute().data or []
        if vec:
            top = vec[0]
            verdict = (
                "COMPATIBLE (self match, high similarity)"
                if top["id"] == s["id"] and top["similarity"] >= 0.9
                else "CHECK — model may not match the stored vectors"
            )
            print(
                f"[2] Self-retrieval: stored id={s['id']} -> top id={top['id']} "
                f"similarity={top['similarity']:.4f}  => {verdict}"
            )
        else:
            print("[2] Self-retrieval: pure-vector RPC returned nothing (unexpected).")
    else:
        print("[2] No rows in documents to test compatibility.")

    # (3) Sample hybrid searches
    for q, dt in SAMPLE_QUERIES:
        print(f"\n=== Q: {q!r}  (doc_type={dt}) ===")
        results = search_documents(q, doc_type=dt, top_k=5)
        if not results:
            print("  (no results)")
        for r in results:
            preview = (r["content"] or "").replace("\n", " ")[:130]
            score = r["score"] if r["score"] is not None else float("nan")
            print(f"  score={score:.4f} [{r['doc_type']}] {r['source_document']}")
            print(f"      {preview}")


if __name__ == "__main__":
    main()
