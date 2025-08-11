from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

import pdfplumber
from bs4 import BeautifulSoup
import pandas as pd


@dataclass
class TableExtraction:
    caption: Optional[str]
    rows: List[List[str]]
    num_rows: int
    num_cols: int


@dataclass
class HtmlExtraction:
    title: str
    meta_description: Optional[str]
    headings: Dict[str, List[str]]
    text: str
    tables: List[TableExtraction] = field(default_factory=list)


@dataclass
class PdfExtraction:
    text: str
    tables: List[pd.DataFrame] = field(default_factory=list)


def extract_html(content: bytes) -> HtmlExtraction:
    soup = BeautifulSoup(content, "lxml")

    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None

    headings = {}
    for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        headings[level] = [h.get_text(" ", strip=True) for h in soup.find_all(level)]

    # Extract human-readable text
    text = soup.get_text("\n", strip=True)

    # Extract tables
    tables: List[TableExtraction] = []
    for table in soup.find_all("table"):
        caption_tag = table.find("caption")
        caption = caption_tag.get_text(" ", strip=True) if caption_tag else None
        rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            row = [c.get_text(" ", strip=True) for c in cells]
            rows.append(row)
        if rows:
            # Infer cols from longest row
            num_cols = max((len(r) for r in rows), default=0)
            tables.append(TableExtraction(caption=caption, rows=rows, num_rows=len(rows), num_cols=num_cols))

    return HtmlExtraction(
        title=title,
        meta_description=meta_description,
        headings=headings,
        text=text,
        tables=tables,
    )


def extract_pdf(content: bytes) -> PdfExtraction:
    # Use pdfplumber to extract text and simple tables
    text_parts: List[str] = []
    tables: List[pd.DataFrame] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                text_parts.append(text)
            try:
                page_tables = page.extract_tables()
                for t in page_tables or []:
                    try:
                        df = pd.DataFrame(t)
                        if not df.empty:
                            tables.append(df)
                    except Exception:
                        continue
            except Exception:
                # Table extraction can be flaky; continue best-effort
                pass
    return PdfExtraction(text="\n\n".join(text_parts).strip(), tables=tables)