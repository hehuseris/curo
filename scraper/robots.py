from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from urllib import robotparser

import httpx


class RobotsCache:
    def __init__(self, user_agent: str, timeout_seconds: float) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self._parsers: Dict[str, robotparser.RobotFileParser] = {}
        self._sitemaps: Dict[str, List[str]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _robots_url_for_origin(self, origin: str) -> str:
        return urljoin(origin, "/robots.txt")

    async def _fetch_and_parse(self, client: httpx.AsyncClient, origin: str) -> None:
        if origin not in self._locks:
            self._locks[origin] = asyncio.Lock()
        async with self._locks[origin]:
            if origin in self._parsers:
                return
            robots_url = self._robots_url_for_origin(origin)
            text = ""
            try:
                resp = await client.get(robots_url, headers={"User-Agent": self.user_agent}, timeout=self.timeout_seconds)
                if resp.status_code < 400:
                    text = resp.text
            except Exception:
                text = ""
            parser = robotparser.RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.parse(text.splitlines())
            except Exception:
                pass
            self._parsers[origin] = parser
            # Extract Sitemap lines manually (robotparser does not expose)
            sitemaps: List[str] = []
            for line in text.splitlines():
                if not line:
                    continue
                lower = line.strip().lower()
                if lower.startswith("sitemap:"):
                    url = line.split(":", 1)[1].strip()
                    if url:
                        sitemaps.append(url)
            self._sitemaps[origin] = sitemaps

    async def allowed(self, client: httpx.AsyncClient, origin: str, url: str) -> bool:
        await self._fetch_and_parse(client, origin)
        parser = self._parsers.get(origin)
        if not parser:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    async def get_sitemaps(self, client: httpx.AsyncClient, origin: str) -> List[str]:
        await self._fetch_and_parse(client, origin)
        return self._sitemaps.get(origin, [])