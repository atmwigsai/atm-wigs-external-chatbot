"""Crawl atmwigs.com into documents(doc_type='website').

DRY-RUN by default (reports only, writes nothing). Add --write to actually insert.

Examples:
  python scripts/crawl_website.py                     # dry-run: static pages + 25 products
  python scripts/crawl_website.py --products 25       # same, explicit
  python scripts/crawl_website.py --no-products       # only company/policy/care pages
  python scripts/crawl_website.py --write --products 25   # actually insert (after review)

Requires OPENAI_API_KEY + SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env.
"""
import argparse
import os
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(os.path.join(ROOT, ".env"))
sys.path.insert(0, ROOT)

from app.crawl import run_crawl  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Crawl atmwigs.com into documents(doc_type=website).")
    ap.add_argument("--write", action="store_true",
                    help="Actually insert rows. Without this, dry-run (reports only).")
    ap.add_argument("--products", type=int, default=25,
                    help="How many product pages to crawl (default 25).")
    ap.add_argument("--no-products", action="store_true",
                    help="Skip product pages (crawl only company/policy pages).")
    ap.add_argument("--care", action="store_true",
                    help="Also crawl the thin care/education hub pages (off by default).")
    ap.add_argument("--posts", type=int, default=0,
                    help="How many blog posts to crawl (default 0 = none).")
    ap.add_argument("--only-posts", action="store_true",
                    help="Crawl ONLY blog posts (skip static + product pages). Use with --posts.")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="Politeness delay between requests, seconds (default 1.0).")
    ap.add_argument("--dedup-threshold", type=float, default=0.95,
                    help="Skip a website chunk if cosine sim to an internal doc >= this (default 0.95).")
    args = ap.parse_args()

    if args.write:
        print("!! --write given: this WILL insert rows into the real documents table "
              "(doc_type='website', insert-only).\n")

    run_crawl(
        product_limit=args.products,
        write=args.write,
        delay=args.delay,
        dedup_threshold=args.dedup_threshold,
        include_products=(not args.no_products) and (not args.only_posts),
        include_care=args.care,
        include_static=not args.only_posts,
        post_limit=args.posts,
    )


if __name__ == "__main__":
    main()
