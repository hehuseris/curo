# Industry-grade Website Scraper (Windows-friendly)

A robust, configurable website scraper and crawler that respects robots.txt, supports sitemaps, concurrency, rate limiting, and exports to JSONL/CSV. Optional JavaScript rendering is powered by Playwright.

## Features
- Respect robots.txt; auto-discovers sitemaps
- Async concurrency with per-domain rate limiting
- URL allow/deny patterns, depth limits, and max pages
- Extracts page title, meta description, text excerpt, and outgoing links
- Export to JSONL and/or CSV
- Optional JS rendering with Playwright
- Windows-friendly installation and usage

## Requirements
- Python 3.10+
- Windows 10/11, macOS, or Linux

## Quickstart (Windows)
1) Create and activate a virtual environment:
```
py -3.10 -m venv .venv
.\.venv\Scripts\activate
```

2) Install dependencies:
```
pip install -r requirements.txt
```

3) (Optional) Install Playwright browsers if you plan to use `--render js`:
```
python -m playwright install
```

4) Run the scraper:
```
python -m scraper --start https://example.com --out data/output.jsonl
```

## CLI Usage
```
python -m scraper --help
```

Examples:
```
# Crawl a site with defaults and export JSONL
python -m scraper --start https://example.com --out data/output.jsonl

# Constrain the crawl to a domain and export CSV
python -m scraper --start https://example.com \
  --allowed-domain example.com \
  --out data/output.csv --format csv

# Use JS rendering (slower) for JS-heavy sites
python -m scraper --start https://example.com --render js --out data/js.jsonl

# Respect robots (default) and discover sitemaps
python -m scraper --start https://example.com --use-sitemaps

# Limit pages and depth
python -m scraper --start https://example.com --max-pages 200 --max-depth 3

# Include/Exclude URL patterns
python -m scraper --start https://example.com --include ".*blog.*" --exclude ".*\?utm.*"
```

## Config via YAML (optional)
You can pass a YAML config file:
```
python -m scraper --config config.example.yaml
```
See `config.example.yaml` for all available options.

## Outputs
- JSONL: Each line is one JSON record
- CSV: Columns: url, status, title, meta_description, text_excerpt, num_links

## Notes
- The scraper respects robots.txt disallow rules. You can disable with `--ignore-robots`.
- Crawl delays from robots are not guaranteed; a general per-domain rate limiter is applied.
- Use `--render js` only when needed; it is slower and requires Playwright browsers installed.

## Development
```
python -m scraper --help
```