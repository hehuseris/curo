import argparse
import asyncio
from pathlib import Path
from typing import List, Optional

from .config import ScraperConfig, load_config_from_yaml, apply_cli_overrides
from .crawler import Crawler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Industry-grade website scraper/crawler (Windows-friendly)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start", nargs="*", help="Start URL(s)")
    parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed domain(s). Repeatable.")
    parser.add_argument("--include", action="append", default=[], help="Regex include pattern(s). Repeatable.")
    parser.add_argument("--exclude", action="append", default=[], help="Regex exclude pattern(s). Repeatable.")
    parser.add_argument("--max-pages", type=int, default=1000, help="Maximum pages to crawl")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum crawl depth")
    parser.add_argument("--concurrency", type=int, default=10, help="Global concurrency")
    parser.add_argument("--per-domain-rate", type=float, default=2.0, help="Approximate requests per second per domain")
    parser.add_argument("--user-agent", default="Mozilla/5.0 (compatible; SimpleScraper/1.0)", help="User-Agent header")
    parser.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt")
    parser.add_argument("--use-sitemaps", action="store_true", help="Discover and enqueue URLs from sitemaps")
    parser.add_argument("--render", choices=["none", "js"], default="none", help="Rendering mode")
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout seconds")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="Output format")
    parser.add_argument("--out", required=True, help="Output file path")
    parser.add_argument("--config", help="YAML config file to load defaults from")
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    base_config = ScraperConfig()

    if args.config:
        base_config = load_config_from_yaml(args.config)

    # Apply CLI overrides
    config = apply_cli_overrides(base_config, args)

    # Ensure output directory exists
    out_path = Path(config.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    crawler = Crawler(config)
    await crawler.run()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()