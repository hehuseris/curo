import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return safe or "item"


def hash_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def canonicalize_url(url: str) -> str:
    url, _frag = urldefrag(url)
    parsed = urlparse(url)
    # Remove default ports
    netloc = parsed.netloc
    if parsed.scheme == "http" and parsed.netloc.endswith(":80"):
        netloc = parsed.netloc.rsplit(":", 1)[0]
    if parsed.scheme == "https" and parsed.netloc.endswith(":443"):
        netloc = parsed.netloc.rsplit(":", 1)[0]
    # Normalize path (remove duplicate slashes)
    path = re.sub(r"/+", "/", parsed.path) or "/"
    normalized = parsed._replace(netloc=netloc, path=path, query=parsed.query)
    return urlunparse(normalized)


def is_same_site(base: str, target: str) -> bool:
    b = urlparse(base)
    t = urlparse(target)
    # Treat subdomains as different sites by default
    return (b.scheme in ("http", "https")) and (b.scheme == t.scheme) and (b.netloc == t.netloc)


def resolve_url(base: str, href: str) -> str:
    if not href:
        return ""
    joined = urljoin(base, href)
    return canonicalize_url(joined)


def get_domain_dirname(start_url: str) -> str:
    p = urlparse(start_url)
    return sanitize_filename(p.netloc)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)