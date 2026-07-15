"""URL selection for the atmwigs.com crawler + robots.txt / English-only filtering.

Scope (agreed): company/info + policy + care/education static pages, plus a subset of product
pages. English canonical URLs only. Respects robots.txt Disallow rules.
"""
import re
from urllib.parse import urlparse

import requests

BASE = "https://atmwigs.com"
USER_AGENT = "ATMWigsBot/1.0 (+internal RAG crawler; contact info@atmwigs.com)"

# Curated English static pages (avoid the many locale variants in the sitemap).
COMPANY_SLUGS = [
    "about-us", "contact-us", "become-our-partner", "membership", "sustainability",
    "ethically", "custom-wigs", "design-your-own-wig-brand", "catalog", "promotion",
    "wear-now-pay-later",
]
POLICY_SLUGS = [
    "returns-refunds-policy", "shipping-policy", "payment-policy", "privacy-policy",
    "cookie-policy", "terms-conditions",
]
CARE_SLUGS = [
    "wig-care-maintenance", "wig-education", "tutorials", "wig-business-insights",
]

PRODUCT_SITEMAPS = [f"{BASE}/product-sitemap1.xml", f"{BASE}/product-sitemap2.xml"]
POST_SITEMAPS = [f"{BASE}/post-sitemap{i}.xml" for i in range(1, 5)]

# robots.txt Disallow (path prefixes / substrings). We only fetch English public pages anyway,
# but this guards every URL before it is crawled.
_DISALLOW_PREFIXES = (
    "/wp-admin/", "/ad-dashboard/", "/wp-login.php", "/wp-content/uploads/wc-logs/",
    "/wp-content/uploads/woocommerce_transient_files/", "/wp-content/uploads/woocommerce_uploads/",
    "/search/", "/feed/", "/author/", "/wig-orders/", "/wig-orders-", "/wp-json/", "/usa/",
    "/my-account/",
)
# Non-English locale prefixes present in the sitemap -> skip (we index English canonical only).
_LOCALE_PREFIXES = ("/nl/", "/ru/", "/es/", "/el/", "/it/", "/fr/", "/ja/", "/de/")


def is_allowed(url: str) -> bool:
    """True if `url` is on atmwigs.com, English, and not blocked by robots.txt."""
    p = urlparse(url)
    if p.netloc and p.netloc.replace("www.", "") != "atmwigs.com":
        return False
    path = p.path or "/"
    tail = path.rsplit("/", 1)[-1]
    if not path.endswith("/") and "." not in tail:  # normalize to trailing slash for prefix match
        path += "/"
    if any(path.startswith(loc) for loc in _LOCALE_PREFIXES):
        return False
    if any(path.startswith(dis) for dis in _DISALLOW_PREFIXES):
        return False
    if "add-to-cart=" in url or re.search(r"[?&]s=", url) or "/feed/" in path:
        return False
    return True


def static_urls(include_care: bool = False) -> list[str]:
    """Curated company + policy English pages. Care/education hubs are thin listing pages
    (real content lives in blog posts), so they're excluded unless include_care=True."""
    slugs = COMPANY_SLUGS + POLICY_SLUGS + (CARE_SLUGS if include_care else [])
    urls = [f"{BASE}/{slug}/" for slug in slugs]
    return [u for u in urls if is_allowed(u)]


def _sitemap_locs(url: str, timeout: float = 20.0) -> list[str]:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return re.findall(r"<loc>([^<]+)</loc>", r.text)


def _sitemap_batch_urls(sitemaps, limit, timeout):
    seen, out = set(), []
    for sm in sitemaps:
        for loc in _sitemap_locs(sm, timeout=timeout):
            loc = loc.strip()
            if loc in seen or not is_allowed(loc):
                continue
            seen.add(loc)
            out.append(loc)
            if limit and len(out) >= limit:
                return out
    return out


def product_urls(limit: int | None = None, timeout: float = 20.0) -> list[str]:
    """Product URLs from the product sitemaps (English canonical, robots-allowed)."""
    return _sitemap_batch_urls(PRODUCT_SITEMAPS, limit, timeout)


def post_urls(limit: int | None = None, timeout: float = 20.0) -> list[str]:
    """Blog post URLs from the post sitemaps (English canonical, robots-allowed)."""
    return _sitemap_batch_urls(POST_SITEMAPS, limit, timeout)
