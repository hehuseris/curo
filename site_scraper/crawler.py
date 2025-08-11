from __future__ import annotations

import asyncio
import json
import mimetypes
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, Optional, Set, List, Any
from urllib.parse import urlparse

import aiohttp
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup

from .extractors import extract_html, extract_pdf
from .utils import (
    resolve_url,
    is_same_site,
    hash_string,
    sanitize_filename,
    ensure_dir,
)


@dataclass
class PageResult:
    id: str
    url: str
    final_url: str
    status: int
    content_type: str
    is_pdf: bool
    html: Optional[Dict[str, Any]]
    pdf: Optional[Dict[str, Any]]
    links: List[str]
    assets: Dict[str, str]
    error: Optional[str] = None


class Crawler:
    def __init__(
        self,
        start_url: str,
        output_dir: Path,
        *,
        concurrency: int = 8,
        delay_seconds: float = 0.0,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
        user_agent: str = "SiteScraper/0.1 (+https://example.com)",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        respect_robots: bool = True,
    ) -> None:
        self.start_url = start_url
        self.output_dir = output_dir
        self.session: Optional[aiohttp.ClientSession] = None
        self.concurrency = concurrency
        self.delay_seconds = delay_seconds
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.user_agent = user_agent
        self.progress_callback = progress_callback or (lambda _: None)
        self.respect_robots = respect_robots

        self.seen: Set[str] = set()
        self.results: List[PageResult] = []
        self.tasks_in_progress = 0
        self.total_discovered = 0

        self.rate_limiter = AsyncLimiter(max(1, concurrency), time_period=1)

        self.base_netloc = urlparse(self.start_url).netloc

        ensure_dir(self.output_dir)
        ensure_dir(self.output_dir / "raw")
        ensure_dir(self.output_dir / "assets" / "pdfs")
        ensure_dir(self.output_dir / "pages")

    async def _fetch(self, url: str) -> Optional[aiohttp.ClientResponse]:
        headers = {"User-Agent": self.user_agent}
        try:
            await self.rate_limiter.acquire()
            resp = await self.session.get(url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=60))
            return resp
        except Exception:
            return None

    async def _process_html(self, url: str, content: bytes, final_url: str) -> PageResult:
        extraction = extract_html(content)
        # Discover links
        soup = BeautifulSoup(content, "lxml")
        links: List[str] = []
        for a in soup.find_all("a"):
            href = a.get("href")
            if not href:
                continue
            abs_url = resolve_url(final_url, href)
            if not abs_url:
                continue
            if is_same_site(self.start_url, abs_url):
                links.append(abs_url)
        page_id = hash_string(final_url)
        # Persist HTML text and tables
        page_dir = self.output_dir / "pages" / page_id
        ensure_dir(page_dir)
        (page_dir / "text.txt").write_text(extraction.text, encoding="utf-8")
        # Save tables as CSVs
        table_files: List[str] = []
        for idx, table in enumerate(extraction.tables):
            csv_path = page_dir / f"table_{idx+1}.csv"
            # Normalize rows into rectangular CSV by padding
            max_cols = table.num_cols
            rows = [row + [""] * (max_cols - len(row)) for row in table.rows]
            # Write CSV
            import csv

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in rows:
                    writer.writerow(row)
            table_files.append(str(csv_path.relative_to(self.output_dir)))
        html_payload: Dict[str, Any] = {
            "title": extraction.title,
            "meta_description": extraction.meta_description,
            "headings": extraction.headings,
            "text_file": str((page_dir / "text.txt").relative_to(self.output_dir)),
            "tables": [
                {
                    "caption": t.caption,
                    "num_rows": t.num_rows,
                    "num_cols": t.num_cols,
                    "csv": table_files[i] if i < len(table_files) else None,
                }
                for i, t in enumerate(extraction.tables)
            ],
        }
        return PageResult(
            id=page_id,
            url=url,
            final_url=final_url,
            status=200,
            content_type="text/html",
            is_pdf=False,
            html=html_payload,
            pdf=None,
            links=links,
            assets={},
        )

    async def _process_pdf(self, url: str, content: bytes, final_url: str) -> PageResult:
        page_id = hash_string(final_url)
        pdf_dir = self.output_dir / "assets" / "pdfs"
        ensure_dir(pdf_dir)
        pdf_filename = f"{page_id}.pdf"
        (pdf_dir / pdf_filename).write_bytes(content)

        extraction = extract_pdf(content)
        # Save text
        text_path = pdf_dir / f"{page_id}.txt"
        text_path.write_text(extraction.text, encoding="utf-8")
        # Save tables
        csv_files: List[str] = []
        for idx, df in enumerate(extraction.tables):
            csv_path = pdf_dir / f"{page_id}_table_{idx+1}.csv"
            df.to_csv(csv_path, index=False)
            csv_files.append(str(csv_path.relative_to(self.output_dir)))
        pdf_payload: Dict[str, Any] = {
            "pdf_file": str((pdf_dir / pdf_filename).relative_to(self.output_dir)),
            "text_file": str(text_path.relative_to(self.output_dir)),
            "tables": csv_files,
        }
        return PageResult(
            id=page_id,
            url=url,
            final_url=final_url,
            status=200,
            content_type="application/pdf",
            is_pdf=True,
            html=None,
            pdf=pdf_payload,
            links=[],
            assets={"pdf": pdf_payload["pdf_file"]},
        )

    async def _worker(self, queue: asyncio.Queue):
        while True:
            try:
                item = await queue.get()
            except asyncio.CancelledError:
                return
            if item is None:
                queue.task_done()
                break
            url, depth = item
            self.tasks_in_progress += 1
            self._notify_progress(current=url)
            try:
                if self.max_pages and len(self.results) >= self.max_pages:
                    queue.task_done()
                    self.tasks_in_progress -= 1
                    continue
                resp = await self._fetch(url)
                if resp is None:
                    self.results.append(
                        PageResult(
                            id=hash_string(url),
                            url=url,
                            final_url=url,
                            status=0,
                            content_type="",
                            is_pdf=False,
                            html=None,
                            pdf=None,
                            links=[],
                            assets={},
                            error="request_failed",
                        )
                    )
                    queue.task_done()
                    self.tasks_in_progress -= 1
                    continue
                final_url = str(resp.url)
                status = resp.status
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if status >= 400:
                    self.results.append(
                        PageResult(
                            id=hash_string(final_url),
                            url=url,
                            final_url=final_url,
                            status=status,
                            content_type=content_type,
                            is_pdf=False,
                            html=None,
                            pdf=None,
                            links=[],
                            assets={},
                            error=f"http_{status}",
                        )
                    )
                else:
                    content = await resp.read()
                    if content_type == "application/pdf" or final_url.lower().endswith(".pdf"):
                        result = await self._process_pdf(url, content, final_url)
                        self.results.append(result)
                    elif content_type.startswith("text/html"):
                        result = await self._process_html(url, content, final_url)
                        self.results.append(result)
                        # Enqueue discovered links
                        next_depth = depth + 1
                        if self.max_depth is None or next_depth <= self.max_depth:
                            for link in result.links:
                                if link not in self.seen and is_same_site(self.start_url, link):
                                    self.seen.add(link)
                                    self.total_discovered += 1
                                    await queue.put((link, next_depth))
                    else:
                        # Unsupported content; ignore but record
                        self.results.append(
                            PageResult(
                                id=hash_string(final_url),
                                url=url,
                                final_url=final_url,
                                status=status,
                                content_type=content_type,
                                is_pdf=False,
                                html=None,
                                pdf=None,
                                links=[],
                                assets={},
                            )
                        )
            except Exception as e:
                self.results.append(
                    PageResult(
                        id=hash_string(url),
                        url=url,
                        final_url=url,
                        status=0,
                        content_type="",
                        is_pdf=False,
                        html=None,
                        pdf=None,
                        links=[],
                        assets={},
                        error=str(e),
                    )
                )
            finally:
                queue.task_done()
                self.tasks_in_progress -= 1
                await asyncio.sleep(self.delay_seconds)
                self._notify_progress()

    def _notify_progress(self, current: Optional[str] = None) -> None:
        self.progress_callback(
            {
                "discovered": self.total_discovered,
                "seen": len(self.seen),
                "processed": len(self.results),
                "in_progress": self.tasks_in_progress,
                "current": current,
            }
        )

    async def crawl(self) -> List[PageResult]:
        self.session = aiohttp.ClientSession()
        try:
            queue: asyncio.Queue = asyncio.Queue()
            start = self.start_url
            self.seen.add(start)
            self.total_discovered = 1
            await queue.put((start, 0))

            workers = [asyncio.create_task(self._worker(queue)) for _ in range(self.concurrency)]

            await queue.join()

            for _ in workers:
                await queue.put(None)
            for w in workers:
                w.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*workers)
        finally:
            await self.session.close()
        return self.results


import contextlib