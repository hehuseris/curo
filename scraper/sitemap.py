from __future__ import annotations

from typing import List, Set
from urllib.parse import urlparse

import httpx
from defusedxml import ElementTree as ET


async def parse_sitemap(client: httpx.AsyncClient, sitemap_url: str, timeout_seconds: float, max_urls: int = 10000) -> List[str]:
    urls: List[str] = []
    try:
        resp = await client.get(sitemap_url, timeout=timeout_seconds)
        if resp.status_code >= 400:
            return urls
        content_type = resp.headers.get("Content-Type", "").lower()
        text = resp.text
        root = ET.fromstring(text)
        tag = root.tag.lower()
        # Namespace handling: trim namespace
        def local_name(t: str) -> str:
            if "}" in t:
                return t.split("}", 1)[1].lower()
            return t.lower()
        root_name = local_name(root.tag)
        if root_name == "urlset":
            for url_elem in root.findall(".//{*}url/{*}loc"):
                if url_elem.text:
                    urls.append(url_elem.text.strip())
                    if len(urls) >= max_urls:
                        break
        elif root_name == "sitemapindex":
            for sm in root.findall(".//{*}sitemap/{*}loc"):
                if sm.text:
                    nested = await parse_sitemap(client, sm.text.strip(), timeout_seconds, max_urls)
                    for u in nested:
                        urls.append(u)
                        if len(urls) >= max_urls:
                            break
        return urls
    except Exception:
        return urls