from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import aiosqlite


SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    status INTEGER,
    title TEXT,
    text TEXT,
    html TEXT,
    headers TEXT,
    fetched_at INTEGER
);
"""


class Storage:
    def __init__(self, db_path: str | None):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def __aenter__(self):
        if self.db_path:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA synchronous=NORMAL;")
            await self._conn.execute(SCHEMA)
            await self._conn.commit()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._conn:
            await self._conn.close()

    async def upsert_page(self, record: Dict[str, Any]) -> None:
        if not self._conn:
            return
        await self._conn.execute(
            """
            INSERT INTO pages (url, status, title, text, html, headers, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                status=excluded.status,
                title=excluded.title,
                text=excluded.text,
                html=excluded.html,
                headers=excluded.headers,
                fetched_at=excluded.fetched_at
            """,
            (
                record.get("url"),
                record.get("status"),
                record.get("title"),
                record.get("text"),
                record.get("html"),
                record.get("headers"),
                record.get("fetched_at"),
            ),
        )
        await self._conn.commit()

    async def list_pages(self) -> List[Dict[str, Any]]:
        if not self._conn:
            return []
        cursor = await self._conn.execute("SELECT url, status, title, text, html, headers, fetched_at FROM pages ORDER BY fetched_at DESC")
        rows = await cursor.fetchall()
        await cursor.close()
        result = []
        for r in rows:
            url, status, title, text, html, headers, fetched_at = r
            headers_obj = {}
            try:
                headers_obj = json.loads(headers) if headers else {}
            except Exception:
                headers_obj = {}
            result.append(
                {
                    "url": url,
                    "status": status,
                    "title": title,
                    "text": text,
                    "html": html,
                    "headers": headers_obj,
                    "fetched_at": fetched_at,
                }
            )
        return result

    async def get_all_urls(self) -> List[str]:
        if not self._conn:
            return []
        cursor = await self._conn.execute("SELECT url FROM pages")
        rows = await cursor.fetchall()
        await cursor.close()
        return [r[0] for r in rows]