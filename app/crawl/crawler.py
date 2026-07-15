"""Crawl atmwigs.com and index pages into documents as doc_type='website'.

Safety model:
- INSERT-only for doc_type='website'. Never modifies/deletes non-website rows.
- URL dedup: re-crawling a URL deletes its previous website rows, then inserts fresh chunks
  (idempotent; picks up content updates).
- Content dedup: a website chunk whose cosine similarity to any existing NON-website doc is
  >= threshold is skipped (avoids duplicating authoritative internal policy/price/catalog text).
- Default is DRY-RUN (reports only). Writing requires write=True (the CLI --write flag).
"""
import json
import time
from datetime import datetime, timezone

import numpy as np

from app.database import get_supabase
from app.rag.embed import embed_texts, EMBEDDING_DIM
from app.crawl.urls import static_urls, product_urls
from app.crawl.extract import fetch_html, extract_main
from app.crawl.chunk import chunk_text

DEFAULT_DEDUP_THRESHOLD = 0.95


def _parse_vec(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return None


def _load_internal_matrix(supabase):
    """Load L2-normalized embeddings of all NON-website docs for content-dedup. (N, dim) or None."""
    rows = (
        supabase.table("documents").select("embedding")
        .neq("doc_type", "website").execute().data or []
    )
    vecs = []
    for r in rows:
        v = _parse_vec(r.get("embedding"))
        if v and len(v) == EMBEDDING_DIM:
            vecs.append(v)
    if not vecs:
        return None
    m = np.asarray(vecs, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _max_internal_sim(vec, internal_norm):
    if internal_norm is None:
        return 0.0
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    if n == 0:
        return 0.0
    sims = internal_norm @ (v / n)   # cosine (rows already L2-normalized)
    return float(sims.max())


def _vec_literal(vec):
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def select_urls(product_limit, include_products=True, include_care=False):
    urls = list(static_urls(include_care=include_care))
    if include_products:
        urls += product_urls(limit=product_limit)
    # de-dup preserving order
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def run_crawl(product_limit=25, write=False, delay=1.0,
              dedup_threshold=DEFAULT_DEDUP_THRESHOLD, include_products=True,
              include_care=False, verbose=True):
    """Crawl selected pages; report what would be inserted (dry-run) or insert (write=True)."""
    supabase = get_supabase()
    if supabase is None:
        raise RuntimeError("Supabase not configured")

    urls = select_urls(product_limit, include_products=include_products, include_care=include_care)
    internal_norm = _load_internal_matrix(supabase)
    if verbose:
        mode = "WRITE" if write else "DRY-RUN"
        internal_n = 0 if internal_norm is None else internal_norm.shape[0]
        print(f"[{mode}] {len(urls)} URLs | dedup vs {internal_n} internal docs "
              f"| threshold={dedup_threshold}\n")

    per_page, total_new, total_dup, total_pages_ok, total_pages_empty = [], 0, 0, 0, 0
    sim_samples = []

    for i, url in enumerate(urls, 1):
        html = fetch_html(url)
        if not html:
            per_page.append((url, "FETCH_FAIL", 0, 0))
            if verbose:
                print(f"  [{i}/{len(urls)}] FETCH_FAIL {url}")
            time.sleep(delay)
            continue
        title, text = extract_main(html, url)
        chunks = chunk_text(text)
        if not chunks:
            total_pages_empty += 1
            per_page.append((url, "NO_TEXT", 0, 0))
            if verbose:
                print(f"  [{i}/{len(urls)}] NO_TEXT   {url}")
            time.sleep(delay)
            continue

        embeddings = embed_texts(chunks)
        kept, dup = [], 0
        for chunk, emb in zip(chunks, embeddings):
            sim = _max_internal_sim(emb, internal_norm)
            sim_samples.append(sim)
            if sim >= dedup_threshold:
                dup += 1
            else:
                kept.append((chunk, emb))
        total_pages_ok += 1
        total_new += len(kept)
        total_dup += dup
        per_page.append((url, title or "(no title)", len(kept), dup))
        if verbose:
            print(f"  [{i}/{len(urls)}] OK  kept={len(kept):2d} dup_skipped={dup:2d}  {url}")

        if write and kept:
            _write_page(supabase, url, title, kept)
        time.sleep(delay)

    summary = {
        "urls": len(urls),
        "pages_ok": total_pages_ok,
        "pages_empty": total_pages_empty,
        "chunks_new": total_new,
        "chunks_dup_skipped": total_dup,
        "written": write,
    }
    if verbose:
        print("\n=== SUMMARY ===")
        print(json.dumps(summary, indent=2))
        if sim_samples:
            arr = np.array(sim_samples)
            print(f"content-similarity vs internal: min={arr.min():.3f} "
                  f"median={np.median(arr):.3f} max={arr.max():.3f} "
                  f"(>= {dedup_threshold} => skipped as duplicate)")
        if not write:
            print("\nDRY-RUN only — nothing written. Re-run with write=True to insert.")
    return summary, per_page


def _write_page(supabase, url, title, kept):
    """Delete previous website rows for this URL, then insert fresh chunks (idempotent)."""
    supabase.table("documents").delete().eq("doc_type", "website").eq("source_document", url).execute()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for idx, (chunk, emb) in enumerate(kept):
        rows.append({
            "content": chunk,
            "chunk_index": idx,
            # doc_type / source_document are derived from metadata by the sync trigger.
            "metadata": {
                "source": "web", "url": url, "title": title or "",
                "crawled_at": now, "doc_type": "website", "source_document": url,
            },
            "embedding": _vec_literal(emb),
        })
    for i in range(0, len(rows), 100):
        supabase.table("documents").insert(rows[i:i + 100]).execute()
