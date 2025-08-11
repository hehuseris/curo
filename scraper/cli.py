from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional

import typer
import yaml
from rich import print
from rich.console import Console
from rich.table import Table

from .crawler import Crawler, CrawlerConfig
from .storage import Storage

app = typer.Typer(help="Async website scraper: crawl, fetch, and export.")
console = Console()


def load_config(config_path: Optional[Path]) -> dict:
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as fp:
        if config_path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(fp) or {}
        elif config_path.suffix.lower() == ".json":
            return json.load(fp) or {}
        else:
            raise typer.BadParameter("Config file must be YAML or JSON")


@app.command()
def crawl(
    start_urls: List[str] = typer.Argument(..., help="One or more starting URLs"),
    config: Optional[Path] = typer.Option(None, "--config", exists=True, help="YAML/JSON config file"),
    max_pages: int = typer.Option(500, help="Maximum pages to crawl"),
    max_depth: int = typer.Option(2, help="Maximum link depth from start URLs"),
    concurrency: int = typer.Option(8, help="Concurrent requests"),
    rate_limit_per_host: float = typer.Option(1.0, help="Requests per second per host"),
    timeout: float = typer.Option(20.0, help="Request timeout seconds"),
    user_agent: str = typer.Option("FullScraper/1.0 (+contact@example.com)", help="User-Agent header"),
    include_domains: List[str] = typer.Option([], help="Allowed registrable domains (defaults to start URL domain)"),
    exclude_regex: Optional[str] = typer.Option(None, help="Exclude URLs matching this regex"),
    output_db: Path = typer.Option(Path("data/scrape.db"), help="SQLite DB path"),
    render_js: bool = typer.Option(False, help="Enable Playwright-based JS rendering"),
    respect_robots: bool = typer.Option(True, help="Respect robots.txt"),
    no_store_html: bool = typer.Option(False, help="Do not store raw HTML (store text only)"),
    resume: bool = typer.Option(True, help="Resume crawl using existing DB to skip seen URLs"),
):
    """Crawl websites starting from one or more URLs."""
    cfg = load_config(config)

    # Merge CLI with config file, CLI takes precedence
    merged = {
        "start_urls": start_urls or cfg.get("start_urls", []),
        "max_pages": max_pages if max_pages is not None else cfg.get("max_pages", 500),
        "max_depth": max_depth if max_depth is not None else cfg.get("max_depth", 2),
        "concurrency": concurrency if concurrency is not None else cfg.get("concurrency", 8),
        "rate_limit_per_host": rate_limit_per_host if rate_limit_per_host is not None else cfg.get("rate_limit_per_host", 1.0),
        "timeout": timeout if timeout is not None else cfg.get("timeout", 20.0),
        "user_agent": user_agent or cfg.get("user_agent"),
        "include_domains": include_domains or cfg.get("include_domains", []),
        "exclude_regex": exclude_regex or cfg.get("exclude_regex"),
        "output_db": str(output_db or Path(cfg.get("output_db", "data/scrape.db"))),
        "render_js": render_js if render_js is not None else cfg.get("render_js", False),
        "respect_robots": respect_robots if respect_robots is not None else cfg.get("respect_robots", True),
        "store_html": not no_store_html if no_store_html is not None else cfg.get("store_html", True),
        "resume": resume if resume is not None else cfg.get("resume", True),
    }

    crawl_config = CrawlerConfig(**merged)

    os.makedirs(Path(merged["output_db"]).parent, exist_ok=True)

    async def _run():
        async with Storage(merged["output_db"]) as storage:
            crawler = Crawler(config=crawl_config, storage=storage)
            total = await crawler.crawl()
            console.print(f"[bold green]Crawl complete[/bold green]: {total} pages stored -> {merged['output_db']}")

    asyncio.run(_run())


@app.command()
def fetch(
    url: str = typer.Argument(..., help="Fetch a single URL and print extracted text"),
    user_agent: str = typer.Option("FullScraper/1.0 (+contact@example.com)"),
    timeout: float = typer.Option(20.0),
    render_js: bool = typer.Option(False),
):
    """Fetch a single URL and print its extracted title and text"""

    async def _run():
        crawler_cfg = CrawlerConfig(
            start_urls=[url],
            max_pages=1,
            max_depth=0,
            concurrency=1,
            rate_limit_per_host=5.0,
            timeout=timeout,
            user_agent=user_agent,
            output_db=None,
            render_js=render_js,
            respect_robots=False,
            store_html=False,
            resume=False,
            include_domains=[],
            exclude_regex=None,
        )
        crawler = Crawler(config=crawler_cfg, storage=None)
        result = await crawler.fetch_and_extract(url)
        if result:
            title = result.get("title")
            text = (result.get("text") or "").strip()
            print(f"[bold]{title}[/bold]\n")
            print(text[:4000])
        else:
            console.print("[red]Failed to fetch.[/red]")

    asyncio.run(_run())


@app.command()
def export(
    db_path: Path = typer.Argument(..., exists=True, help="Path to SQLite DB"),
    out: Path = typer.Option(Path("pages.json"), help="Output file path"),
    format: str = typer.Option("json", help="json or csv"),
):
    """Export stored pages to JSON or CSV"""

    async def _run():
        async with Storage(str(db_path)) as storage:
            rows = await storage.list_pages()
            if format.lower() == "json":
                with open(out, "w", encoding="utf-8") as fp:
                    json.dump(rows, fp, ensure_ascii=False)
            elif format.lower() == "csv":
                import csv

                fieldnames = list(rows[0].keys()) if rows else []
                with open(out, "w", encoding="utf-8", newline="") as fp:
                    writer = csv.DictWriter(fp, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
            else:
                raise typer.BadParameter("format must be 'json' or 'csv'")

            table = Table(title="Export Summary")
            table.add_column("Output")
            table.add_column("Count")
            table.add_row(str(out), str(len(rows)))
            console.print(table)

    asyncio.run(_run())