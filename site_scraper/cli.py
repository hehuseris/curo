from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from .crawler import Crawler, PageResult
from .report import write_report
from .utils import get_domain_dirname, ensure_dir

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def scrape(
    url: str = typer.Argument(..., help="Starting URL for the crawl"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    concurrency: int = typer.Option(8, help="Concurrent requests"),
    delay: float = typer.Option(0.0, help="Politeness delay between requests per worker (seconds)"),
    max_pages: Optional[int] = typer.Option(None, help="Max pages to fetch"),
    max_depth: Optional[int] = typer.Option(None, help="Max crawl depth (0 = only the start page)"),
    user_agent: str = typer.Option("SiteScraper/0.1 (+https://example.com)", help="User-Agent header"),
    no_report: bool = typer.Option(False, help="Skip generating HTML report"),
) -> None:
    """Scrape a website (HTML pages and PDFs), extract tables, and generate a clean report."""

    start_time = datetime.utcnow()
    ts = start_time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output) if output else Path.cwd() / "scrapes" / f"{get_domain_dirname(url)}__{ts}"
    ensure_dir(out_dir)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("Processed: {task.completed} / ~{task.total}"),
        TimeElapsedColumn(),
        transient=False,
        console=console,
    )

    # Because total is unknown, we will update it dynamically to discovered count
    task_id = progress.add_task("Crawling", total=1)

    def on_progress(state: Dict[str, Any]) -> None:
        total = max(1, state.get("discovered", 1))
        processed = state.get("processed", 0)
        current = state.get("current") or ""
        progress.update(task_id, total=total, completed=processed, description=f"Crawling {current[:80]}")

    crawler = Crawler(
        start_url=url,
        output_dir=out_dir,
        concurrency=concurrency,
        delay_seconds=delay,
        max_pages=max_pages,
        max_depth=max_depth,
        user_agent=user_agent,
        progress_callback=on_progress,
    )

    with progress:
        results: List[PageResult] = asyncio.run(crawler.crawl())

    # Persist machine-readable JSON
    results_json = [
        {
            "id": r.id,
            "url": r.url,
            "final_url": r.final_url,
            "status": r.status,
            "content_type": r.content_type,
            "is_pdf": r.is_pdf,
            "html": r.html,
            "pdf": r.pdf,
            "links": r.links,
            "assets": r.assets,
            "error": r.error,
        }
        for r in results
    ]
    (out_dir / "results.json").write_text(json.dumps(results_json, indent=2), encoding="utf-8")

    if not no_report:
        summary = {
            "start_url": url,
            "started_at": start_time.isoformat() + "Z",
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "num_pages": len(results),
            "num_errors": sum(1 for r in results if r.error),
            "output_dir": str(out_dir),
        }
        pages_payload = [
            {
                "id": r.id,
                "url": r.url,
                "final_url": r.final_url,
                "status": r.status,
                "content_type": r.content_type,
                "is_pdf": r.is_pdf,
                "title": (r.html or {}).get("title") if r.html else None,
                "text_file": (r.html or {}).get("text_file") if r.html else (r.pdf or {}).get("text_file"),
                "tables": (r.html or {}).get("tables") if r.html else (r.pdf or {}).get("tables"),
                "pdf_file": (r.pdf or {}).get("pdf_file") if r.pdf else None,
                "error": r.error,
            }
            for r in results
        ]
        write_report(out_dir, summary, pages_payload)

    console.print(f"\n[bold green]Done.[/bold green] Output in: {out_dir}")


if __name__ == "__main__":
    app()