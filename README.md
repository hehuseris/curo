# Full-Featured Web Scraper (Async, CLI)

A production-ready, async web scraper with:

- Robots.txt compliance and domain scoping
- Rate limiting, concurrency control, retries and timeouts
- HTML parsing and boilerplate removal (readability) for clean text
- SQLite storage (HTML, text, title, headers, status, metadata)
- Export to JSON/CSV
- Optional JavaScript rendering via Playwright
- Resume and deduping of URLs
- Config via CLI flags or YAML

## Quickstart

1) Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Easiest: paste a URL and go

```bash
python -m scraper https://example.com
```

This will crawl up to 200 pages (depth 2) and write to `data/scrape.db`.

3) Full control (CLI):

```bash
python -m scraper crawl https://example.com \
  --max-pages 200 --max-depth 2 \
  --concurrency 8 --rate-limit 1 \
  --output-db data/scrape.db
```

4) Export results:

```bash
python -m scraper export data/scrape.db --format json --out pages.json
python -m scraper export data/scrape.db --format csv --out pages.csv
```

5) Optional: JavaScript rendering

```bash
pip install playwright
playwright install
python -m scraper crawl https://example.com --render-js
```

## CLI

```bash
python -m scraper --help
python -m scraper crawl --help
python -m scraper export --help
```

## Configuration via YAML (optional)

Example `config.yaml`:

```yaml
start_urls:
  - https://example.com
max_pages: 300
max_depth: 2
concurrency: 10
rate_limit_per_host: 1
respect_robots: true
user_agent: "MyScraper/1.0 (+contact@example.com)"
include_domains:
  - example.com
exclude_regex: null
render_js: false
output_db: data/scrape.db
```

Run with:

```bash
python -m scraper crawl --config config.yaml
```

## Docker

```bash
docker build -t scraper .
docker run --rm -v $(pwd)/data:/app/data scraper python -m scraper crawl https://example.com --output-db data/scrape.db
```

## Notes

- Use `--respect-robots/--no-respect-robots` to control robots.txt behavior (defaults to respecting).
- Use `--include-domains` to restrict to certain domains; otherwise defaults to the start URL's registrable domain.
- For large crawls, prefer lower concurrency and a rate limit of 1-2 req/s per host to be polite.