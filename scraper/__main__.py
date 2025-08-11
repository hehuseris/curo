from .cli import app

# Simple one-argument mode: `python -m scraper https://example.com`
# Falls back to the Typer CLI for all other usages.
if __name__ == "__main__":
    import sys
    import os
    import asyncio
    from pathlib import Path
    from rich.console import Console

    if len(sys.argv) == 2 and sys.argv[1].startswith(("http://", "https://")):
        url = sys.argv[1]
        console = Console()
        from .crawler import Crawler, CrawlerConfig
        from .storage import Storage

        async def _run_simple(url_: str):
            output_db = "data/scrape.db"
            os.makedirs(Path(output_db).parent, exist_ok=True)
            cfg = CrawlerConfig(
                start_urls=[url_],
                max_pages=200,
                max_depth=2,
                concurrency=8,
                rate_limit_per_host=1.0,
                timeout=20.0,
                user_agent="FullScraper/1.0 (+contact@example.com)",
                output_db=output_db,
                render_js=False,
                respect_robots=True,
                store_html=True,
                resume=True,
            )
            async with Storage(output_db) as storage:
                crawler = Crawler(config=cfg, storage=storage)
                total = await crawler.crawl()
                console.print(f"[bold green]Done[/bold green] {total} pages -> {output_db}")

        asyncio.run(_run_simple(url))
    else:
        app()