from __future__ import annotations

from typing import Tuple

from bs4 import BeautifulSoup
from readability import Document


def extract_readable(html: str, url: str) -> Tuple[str, str]:
    if not html:
        return "", ""
    try:
        doc = Document(html)
        title = doc.short_title() or ""
        cleaned_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(cleaned_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        return title, text
    except Exception:
        try:
            soup = BeautifulSoup(html, "lxml")
            title = (soup.title.string or "").strip() if soup.title else ""
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return title, text
        except Exception:
            return "", ""