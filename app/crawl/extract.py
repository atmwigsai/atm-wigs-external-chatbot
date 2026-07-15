"""Fetch a page and extract its main text content (boilerplate removed) via trafilatura."""
import re

import requests
import trafilatura

from app.crawl.urls import USER_AGENT


def fetch_html(url: str, timeout: float = 25.0) -> str | None:
    """Politely fetch a page's HTML. Returns None on error/non-200/non-HTML."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    if "text/html" not in r.headers.get("Content-Type", ""):
        return None
    return r.text


def extract_main(html: str, url: str) -> tuple[str, str]:
    """Return (title, main_text) extracted from HTML. main_text is '' if nothing usable."""
    text = trafilatura.extract(
        html, url=url, favor_precision=True,
        include_comments=False, include_tables=True,
    ) or ""

    title = ""
    try:
        meta = trafilatura.extract_metadata(html)
        if meta and meta.title:
            title = meta.title
    except Exception:
        pass
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

    return title.strip(), text.strip()
