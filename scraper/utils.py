from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from selectolax.parser import HTMLParser


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    # Remove fragment
    new = parsed._replace(scheme=scheme, netloc=netloc, fragment="")
    return urlunparse(new)


def url_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_allowed_by_patterns(url: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    for pattern in exclude_patterns:
        if re.search(pattern, url):
            return False
    if not include_patterns:
        return True
    for pattern in include_patterns:
        if re.search(pattern, url):
            return True
    return False


def is_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    if not allowed_domains:
        return True
    domain = url_domain(url)
    return any(domain == d or domain.endswith("." + d) for d in allowed_domains)


def extract_links(base_url: str, html: str) -> List[str]:
    doc = HTMLParser(html)
    links: List[str] = []
    for a in doc.css("a[href]"):
        href = a.attributes.get("href")
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        links.append(abs_url)
    return links