from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import yaml


@dataclass
class ScraperConfig:
    start_urls: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)

    max_pages: int = 1000
    max_depth: int = 5

    concurrency: int = 10
    per_domain_rps: float = 2.0
    user_agent: str = "Mozilla/5.0 (compatible; SimpleScraper/1.0)"
    obey_robots: bool = True
    use_sitemaps: bool = False
    render_mode: str = "none"  # "none" | "js"
    timeout_seconds: float = 20.0

    output_format: str = "jsonl"  # "jsonl" | "csv"
    output_path: str = "data/output.jsonl"


def load_config_from_yaml(path: str) -> ScraperConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = ScraperConfig(**{k: v for k, v in data.items() if k in ScraperConfig.__annotations__})
    return cfg


def apply_cli_overrides(config: ScraperConfig, args) -> ScraperConfig:
    cfg = ScraperConfig(**config.__dict__)

    if args.start:
        cfg.start_urls = args.start
    if args.allowed_domain:
        cfg.allowed_domains = args.allowed_domain
    if args.include:
        cfg.include_patterns = args.include
    if args.exclude:
        cfg.exclude_patterns = args.exclude

    if args.max_pages is not None:
        cfg.max_pages = args.max_pages
    if args.max_depth is not None:
        cfg.max_depth = args.max_depth

    if args.concurrency is not None:
        cfg.concurrency = args.concurrency
    if args.per_domain_rate is not None:
        cfg.per_domain_rps = args.per_domain_rate
    if args.user_agent:
        cfg.user_agent = args.user_agent
    if args.ignore_robots:
        cfg.obey_robots = False
    if args.use_sitemaps:
        cfg.use_sitemaps = True
    if args.render:
        cfg.render_mode = args.render
    if args.timeout is not None:
        cfg.timeout_seconds = args.timeout

    if args.format:
        cfg.output_format = args.format
    if args.out:
        cfg.output_path = args.out

    return cfg