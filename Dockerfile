FROM python:3.11-slim

WORKDIR /app

# System deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper ./scraper
COPY README.md ./

# Optional playwright dependencies (uncomment if you want JS rendering in container)
# RUN pip install playwright && playwright install --with-deps

ENTRYPOINT ["python", "-m", "scraper"]