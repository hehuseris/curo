# Site Scraper (Async, with PDF/table extraction and clean reports)

Features
- Crawl an entire site (same origin), async + concurrent
- Extract HTML text, headings, and tables
- Download and parse PDFs (text + tables)
- Persist clean, structured outputs (JSON, CSV, TXT)
- Generate a beautiful static HTML report
- Live progress bar with current URL

## Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the scraper:

```bash
python -m site_scraper.cli scrape https://example.com -o ./output --concurrency 8 --max-depth 2 --max-pages 200
```

3. Open the report:

- Open `output/report/index.html` in your browser.

## CLI options

- `url` (arg): Start URL
- `--output, -o`: Output directory (default: `./scrapes/<domain>__<timestamp>`)
- `--concurrency`: Concurrent requests (default 8)
- `--delay`: Delay between requests per worker (seconds)
- `--max-pages`: Max pages to fetch
- `--max-depth`: Max crawl depth
- `--user-agent`: User-Agent header
- `--no-report`: Skip report generation

## Output structure

```
<output>/
  results.json              # Machine-readable summary
  pages/<page_id>/          # Per-page extracted artifacts
    text.txt
    table_1.csv
    ...
  assets/pdfs/
    <id>.pdf
    <id>.txt
    <id>_table_1.csv
  report/
    index.html
    pages/<id>.html
    styles.css
```

Notes
- The crawler stays within the same origin (scheme + host + port).
- PDFs are processed best-effort; complex layouts may not extract perfectly.
- Respect target sites' robots and terms of service.