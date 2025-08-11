from __future__ import annotations

import asyncio
from typing import Dict
from urllib.parse import urlparse, urljoin
import urllib.robotparser as robotparser

import httpx


class RobotsCache:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.cache: Dict[str, robotparser.RobotFileParser] = {}
        self.lock = asyncio.Lock()

    async def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = await self._get_or_fetch(base)
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True

    async def _get_or_fetch(self, base: str) -> robotparser.RobotFileParser:
        async with self.lock:
            if base in self.cache:
                return self.cache[base]

            robots_url = urljoin(base, "/robots.txt")
            rp = robotparser.RobotFileParser()
            rp.set_url(robots_url)

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(robots_url, follow_redirects=True)
                    if resp.status_code == 200 and resp.text:
                        rp.parse(resp.text.splitlines())
                    else:
                        # No robots.txt => allow
                        rp.parse([])
            except Exception:
                rp.parse([])

            self.cache[base] = rp
            return rp