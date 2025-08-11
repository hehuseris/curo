from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def write_report(output_dir: Path, crawl_summary: Dict[str, Any], pages: List[Dict[str, Any]]) -> None:
    templates_dir = Path(__file__).parent / "templates"
    env = _env(templates_dir)

    # Ensure directories
    (output_dir / "report").mkdir(parents=True, exist_ok=True)

    index_tmpl = env.get_template("index.html")
    page_tmpl = env.get_template("page.html")

    # Write index
    (output_dir / "report" / "index.html").write_text(
        index_tmpl.render(summary=crawl_summary, pages=pages),
        encoding="utf-8",
    )

    # Write each page
    for page in pages:
        page_dir = output_dir / "report" / "pages"
        page_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{page['id']}.html"
        (page_dir / filename).write_text(
            page_tmpl.render(page=page),
            encoding="utf-8",
        )

    # Write a lightweight stylesheet
    css = (
        "body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;line-height:1.5;padding:24px;}"
        "a{color:#0d6efd;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".container{max-width:1200px;margin:0 auto;}"
        ".grid{display:grid;grid-template-columns:1fr 320px;gap:24px;}"
        ".card{border:1px solid #e5e7eb;border-radius:12px;padding:16px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.04);}"
        ".muted{color:#6b7280;} .badge{display:inline-block;padding:2px 8px;border-radius:999px;background:#f3f4f6;font-size:12px;}"
        "table{border-collapse:collapse;width:100%;} th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;} th{background:#f9fafb;}"
        ".table-wrap{overflow:auto;border:1px solid #e5e7eb;border-radius:8px;margin:12px 0;}"
        ".header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}"
        ".code{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace;}"
    )
    (output_dir / "report" / "styles.css").write_text(css, encoding="utf-8")