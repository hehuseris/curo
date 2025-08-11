from __future__ import annotations

import asyncio
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Set, Tuple

import httpx
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential
import tldextract

from .extractors import extract_readable
from .robots import RobotsCache
from .storage import Storage


@dataclass
class CrawlerConfig:
    start_urls: list[str]
    max_pages: int = 500
    max_depth: int = 2
    concurrency: int = 8
    rate_limit_per_host: float = 1.0
    timeout: float = 20.0
    user_agent: str = "FullScraper/1.0 (+contact@example.com)"
    include_domains: list[str] = field(default_factory=list)
    exclude_regex: Optional[str] = None
    output_db: Optional[str] = "data/scrape.db"
    render_js: bool = False
    respect_robots: bool = True
    store_html: bool = True
    resume: bool = True


class Crawler:
    def __init__(self, config: CrawlerConfig, storage: Optional[Storage]):
        self.config = config
        self.storage = storage
        self.session: Optional[httpx.AsyncClient] = None
        self.robots = RobotsCache(user_agent=self.config.user_agent) if self.config.respect_robots else None
        self.per_host_limiter: Dict[str, AsyncLimiter] = {}
        self.concurrency_semaphore = asyncio.Semaphore(self.config.concurrency)
        self.queue: Deque[Tuple[str, int]] = deque((url, 0) for url in self.config.start_urls)
        self.seen: Set[str] = set()
        self.domain_whitelist: Set[str] = self._compute_domain_whitelist()
        self.exclude_pattern = re.compile(self.config.exclude_regex) if self.config.exclude_regex else None

    def _compute_domain_whitelist(self) -> Set[str]:
        if self.config.include_domains:
            return set(self.config.include_domains)
        # Default to start URL registrable domain
        domains = set()
        for url in self.config.start_urls:
            ext = tldextract.extract(url)
            if ext.registered_domain:
                domains.add(ext.registered_domain)
        return domains

    async def _get_session(self) -> httpx.AsyncClient:
        if self.session is None:
            headers = {"User-Agent": self.config.user_agent}
            self.session = httpx.AsyncClient(
                headers=headers,
                timeout=self.config.timeout,
                follow_redirects=True,
                http2=True,
            )
        return self.session

    async def _ensure_robots(self, url: str) -> bool:
        if not self.robots:
            return True
        return await self.robots.can_fetch(url)

    def _should_enqueue(self, url: str) -> bool:
        if url in self.seen:
            return False
        if self.exclude_pattern and self.exclude_pattern.search(url):
            return False
        if self.domain_whitelist:
            ext = tldextract.extract(url)
            domain = ext.registered_domain
            if domain and domain not in self.domain_whitelist:
                return False
        return True

    def _normalize_url(self, base_url: str, href: str) -> Optional[str]:
        try:
            from urllib.parse import urljoin, urldefrag

            if not href:
                return None
            absolute = urljoin(base_url, href)
            if not absolute.startswith(("http://", "https://")):
                return None
            absolute, _frag = urldefrag(absolute)
            # strip trailing slash for normalization
            if absolute.endswith("/"):
                absolute = absolute[:-1]
            return absolute
        except Exception:
            return None

    def _get_host(self, url: str) -> str:
        from urllib.parse import urlparse

        return urlparse(url).netloc

    def _get_limiter(self, url: str) -> AsyncLimiter:
        host = self._get_host(url)
        limiter = self.per_host_limiter.get(host)
        if not limiter:
            # rate_limit_per_host is requests per second
            rate = self.config.rate_limit_per_host
            limiter = AsyncLimiter(max_rate=rate, time_period=1)
            self.per_host_limiter[host] = limiter
        return limiter

    async def crawl(self) -> int:
        stored = 0
        # Resume support: mark seen from DB
        if self.storage and self.config.resume:
            existing = await self.storage.get_all_urls()
            self.seen.update(existing)

        session = await self._get_session()

        async def worker():
            nonlocal stored
            while self.queue and len(self.seen) < self.config.max_pages:
                url, depth = self.queue.popleft()
                if url in self.seen:
                    continue
                self.seen.add(url)

                if self.robots and not await self._ensure_robots(url):
                    continue

                async with self.concurrency_semaphore:
                    limiter = self._get_limiter(url)
                    async with limiter:
                        result = await self.fetch_and_extract(url)
                if not result:
                    continue
                if self.storage:
                    await self.storage.upsert_page(result)
                    stored += 1

                # Enqueue links
                if depth < self.config.max_depth:
                    for link in result.get("links", []):
                        if self._should_enqueue(link):
                            self.queue.append((link, depth + 1))

        workers = [asyncio.create_task(worker()) for _ in range(self.config.concurrency)]
        await asyncio.gather(*workers)

        if session:
            await session.aclose()
        return stored

    async def fetch_and_extract(self, url: str) -> Optional[Dict[str, Any]]:
        session = await self._get_session()

        async def _fetch_html() -> Optional[Tuple[int, str, Dict[str, Any]]]:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
                retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
            ):
                with attempt:
                    resp = await session.get(url)
                    status = resp.status_code
                    if status >= 400:
                        return status, "", {"headers": dict(resp.headers)}
                    return status, resp.text, {"headers": dict(resp.headers)}
            return None

        async def _fetch_html_js() -> Optional[Tuple[int, str, Dict[str, Any]]]:
            try:
                from playwright.async_api import async_playwright
            except Exception:
                return await _fetch_html()

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(user_agent=self.config.user_agent)
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=int(self.config.timeout * 1000))
                    content = await page.content()
                    status = page.status or 200
                    headers = {}  # Playwright does not expose response headers easily after goto
                    await browser.close()
                    return status, content, {"headers": headers}
            except Exception:
                return await _fetch_html()

        fetched: Optional[Tuple[int, str, Dict[str, Any]]] = (
            await _fetch_html_js() if self.config.render_js else await _fetch_html()
        )
        if not fetched:
            return None
        status, html, meta = fetched
        fetched_at = int(time.time())

        title, text = extract_readable(html, url)
        links = self._extract_links(html, url)

        record: Dict[str, Any] = {
            "url": url,
            "status": status,
            "title": title,
            "text": text,
            "html": html if self.config.store_html else None,
            "headers": json.dumps(meta.get("headers", {})),
            "fetched_at": fetched_at,
            "links": links,
        }
        return record

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        try:
            soup = BeautifulSoup(html, "lxml")
            links: list[str] = []
            for a in soup.find_all("a", href=True):
                normalized = self._normalize_url(base_url, a.get("href"))
                if normalized:
                    links.append(normalized)
            # de-duplicate while preserving order
            seen_local: Set[str] = set()
            unique_links = []
            for link in links:
                if link not in seen_local:
                    unique_links.append(link)
                    seen_local.add(link)
            return unique_links
        except Exception:
            return []