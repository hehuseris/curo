from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from aiolimiter import AsyncLimiter

from .config import ScraperConfig
from .utils import normalize_url, url_domain, is_domain_allowed, is_allowed_by_patterns, extract_links
from .robots import RobotsCache
from .sitemap import parse_sitemap
from .extractor import extract_page
from .storage import JSONLWriter, CSVWriter


@dataclass
class QueueItem:
    url: str
    depth: int


class Crawler:
    def __init__(self, config: ScraperConfig) -> None:
        self.cfg = config
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self.visited: Set[str] = set()
        self.domain_limiters: Dict[str, AsyncLimiter] = {}
        self.robots = RobotsCache(user_agent=self.cfg.user_agent, timeout_seconds=self.cfg.timeout_seconds)
        self.total_processed = 0

    async def run(self) -> None:
        if not self.cfg.start_urls:
            raise SystemExit("No --start URLs provided and no config start_urls")

        for url in self.cfg.start_urls:
            await self.queue.put(QueueItem(url=normalize_url(url), depth=0))

        limits = httpx.Limits(max_connections=self.cfg.concurrency, max_keepalive_connections=self.cfg.concurrency)
        async with httpx.AsyncClient(http2=True, timeout=self.cfg.timeout_seconds, limits=limits, follow_redirects=True) as client:
            if self.cfg.use_sitemaps:
                await self._enqueue_sitemaps(client)

            workers = [asyncio.create_task(self._worker(client)) for _ in range(self.cfg.concurrency)]
            await self.queue.join()
            for w in workers:
                w.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*workers)

    async def _enqueue_sitemaps(self, client: httpx.AsyncClient) -> None:
        origins: Set[str] = set()
        for u in self.cfg.start_urls:
            parsed = urlparse(u)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            origins.add(origin)
        for origin in origins:
            sitemaps = await self.robots.get_sitemaps(client, origin)
            for sm in sitemaps:
                urls = await parse_sitemap(client, sm, self.cfg.timeout_seconds, max_urls=self.cfg.max_pages)
                for u in urls:
                    await self.queue.put(QueueItem(url=normalize_url(u), depth=0))

    async def _worker(self, client: httpx.AsyncClient) -> None:
        while True:
            item = await self.queue.get()
            try:
                if self.total_processed >= self.cfg.max_pages:
                    return
                await self._process_item(client, item)
            finally:
                self.queue.task_done()

    def _get_domain_limiter(self, url: str) -> AsyncLimiter:
        domain = url_domain(url)
        limiter = self.domain_limiters.get(domain)
        if limiter is None:
            # per_domain_rps tokens per second
            rate = max(self.cfg.per_domain_rps, 0.1)
            limiter = AsyncLimiter(max_rate=rate, time_period=1.0)
            self.domain_limiters[domain] = limiter
        return limiter

    async def _process_item(self, client: httpx.AsyncClient, item: QueueItem) -> None:
        url = normalize_url(item.url)
        if url in self.visited:
            return

        if not is_domain_allowed(url, self.cfg.allowed_domains):
            return
        if not is_allowed_by_patterns(url, self.cfg.include_patterns, self.cfg.exclude_patterns):
            return

        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if self.cfg.obey_robots:
            allowed = await self.robots.allowed(client, origin, url)
            if not allowed:
                return

        limiter = self._get_domain_limiter(url)
        async with limiter:
            status, html = await self._fetch(client, url)

        self.visited.add(url)
        self.total_processed += 1

        record = {
            "url": url,
            "status": status,
        }

        if html:
            data = extract_page(url, html)
            record.update(data)

            if item.depth < self.cfg.max_depth and self.total_processed < self.cfg.max_pages:
                for link in extract_links(url, html):
                    if link not in self.visited:
                        await self.queue.put(QueueItem(url=normalize_url(link), depth=item.depth + 1))

        await self._write_output(record)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Tuple[int, Optional[str]]:
        if self.cfg.render_mode == "js":
            try:
                return await self._fetch_with_playwright(url)
            except ImportError:
                # Fallback to HTTP fetch if Playwright not installed
                pass
        try:
            resp = await client.get(url, headers={"User-Agent": self.cfg.user_agent})
            if resp.status_code >= 400:
                return resp.status_code, None
            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                return resp.status_code, resp.text
            else:
                return resp.status_code, None
        except Exception:
            return 0, None

    async def _fetch_with_playwright(self, url: str) -> Tuple[int, Optional[str]]:
        from playwright.async_api import async_playwright
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.cfg.user_agent)
                page = await context.new_page()
                resp = await page.goto(url, wait_until="load", timeout=int(self.cfg.timeout_seconds * 1000))
                status = resp.status if resp else 0
                html = await page.content()
                await context.close()
                await browser.close()
                return status, html
        except Exception:
            return 0, None

    async def _write_output(self, record: Dict) -> None:
        # Lazy init writer and keep open across calls via instance attribute
        if not hasattr(self, "_writer"):
            if self.cfg.output_format == "csv":
                self._writer = CSVWriter(self.cfg.output_path)
            else:
                self._writer = JSONLWriter(self.cfg.output_path)
        self._writer.write(record)