from __future__ import annotations

from typing import Dict, List
from selectolax.parser import HTMLParser

from .utils import extract_links


def extract_page(url: str, html: str) -> Dict:
    doc = HTMLParser(html)
    title = None
    title_node = doc.css_first("title")
    if title_node:
        title = title_node.text(strip=True)

    meta_desc = None
    md = doc.css_first('meta[name="description"]') or doc.css_first('meta[property="og:description"]')
    if md:
        meta_desc = md.attributes.get("content")

    # Create a simple text excerpt
    # Selectolax text() returns combined text content
    text = doc.text()
    text_excerpt = (text or "").strip().replace("\n", " ")[:500]

    links = extract_links(url, html)

    return {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "text_excerpt": text_excerpt,
        "num_links": len(links),
        "links": links,
    }