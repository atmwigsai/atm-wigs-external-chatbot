"""Website crawler for the ATM Wigs knowledge base (Phase 3).

Crawls atmwigs.com and indexes pages into the `documents` table as doc_type='website', for use
by the `web_search_atmwigs` agent tool. Run via scripts/crawl_website.py (dry-run by default).
"""
from app.crawl.crawler import run_crawl

__all__ = ["run_crawl"]
