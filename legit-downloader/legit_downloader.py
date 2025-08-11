#!/usr/bin/env python3

"""
Legit Downloader (Windows-friendly)

This tool downloads files you are legally allowed to access. It DOES NOT bypass DRM,
remove encryption, or circumvent access controls. Use only with content you own or
have permission to download and in compliance with the source website's terms.

Features:
- Single URL or list of URLs
- Resume (single-connection) if the server supports Range
- Parallel chunked downloads for faster throughput when Range is supported
- Retries with exponential backoff
- Custom headers (e.g., Authorization) for authorized downloads
- Progress bars

Notes:
- Encrypted/DRM-protected streams (e.g., Widevine, PlayReady, FairPlay, encrypted HLS/DASH)
  are NOT supported by this tool.
- HLS/DASH manifests may be downloadable only if they are clear (not encrypted) and allowed
  by the site's terms; this script focuses on direct file downloads.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import math
import os
import re
import sys
import time
import typing as t
from pathlib import Path

import requests
from requests import Response
from tqdm import tqdm

DEFAULT_CONNECTIONS = 8
DEFAULT_CHUNK_SIZE_BYTES = 8 * 1024 * 1024  # 8 MiB
DEFAULT_STREAM_CHUNK_BYTES = 64 * 1024  # 64 KiB for streaming writes
DEFAULT_RETRIES = 5
DEFAULT_TIMEOUT = 30  # seconds


class DownloadError(Exception):
    pass


def parse_kv_header(header_value: str) -> t.Tuple[str, str]:
    if ":" not in header_value:
        raise ValueError("Header must be in 'Key: Value' format")
    key, value = header_value.split(":", 1)
    return key.strip(), value.strip()


def sanitize_filename(name: str) -> str:
    # Windows-safe file name sanitation
    name = name.strip().replace("\\", "_").replace("/", "_").replace(":", "_")
    name = name.replace("*", "_").replace("?", "_").replace("\"", "'")
    name = name.replace("<", "_").replace(">", "_").replace("|", "_")

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)

    # Prevent empty names
    if not name:
        name = "download.bin"
    return name


def filename_from_content_disposition(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    # Try RFC 5987 filename*
    match_ext = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", content_disposition, re.IGNORECASE)
    if match_ext:
        value = match_ext.group(1)
        try:
            return requests.utils.unquote(value)
        except Exception:
            return value
    # Try simple filename="..."
    match_simple = re.search(r"filename\s*=\s*\"([^\"]+)\"", content_disposition, re.IGNORECASE)
    if match_simple:
        return match_simple.group(1)
    # Try filename=...
    match_bare = re.search(r"filename\s*=\s*([^;]+)", content_disposition, re.IGNORECASE)
    if match_bare:
        return match_bare.group(1).strip().strip("\"")
    return None


def guess_filename_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse

        path = urlparse(url).path
        if path and path != "/":
            candidate = os.path.basename(path)
            if candidate:
                return candidate
    except Exception:
        pass
    return "download.bin"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def backoff_sleep(attempt: int) -> None:
    # Exponential backoff with jitter
    base = min(2 ** attempt, 32)
    time.sleep(base * (0.5 + 0.5 * os.urandom(1)[0] / 255.0))


def get_head_or_probe(session: requests.Session, url: str, timeout: int, headers: dict[str, str]) -> Response:
    # Try HEAD first
    try:
        resp = session.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if resp.status_code < 400:
            return resp
    except requests.RequestException:
        pass

    # Fallback: GET first byte to probe support
    probe_headers = dict(headers)
    probe_headers["Range"] = "bytes=0-0"
    resp = session.get(url, allow_redirects=True, timeout=timeout, headers=probe_headers, stream=True)
    return resp


def get_total_and_range_support(resp: Response) -> tuple[int | None, bool]:
    total: int | None = None
    accept_ranges = False

    # Content-Length may be present
    cl = resp.headers.get("Content-Length")
    if cl and cl.isdigit():
        total = int(cl)

    # Accept-Ranges: bytes indicates support
    ar = resp.headers.get("Accept-Ranges", "").lower()
    if "bytes" in ar:
        accept_ranges = True

    # If we probed with Range, Content-Range should be present
    cr = resp.headers.get("Content-Range")
    if cr and "/" in cr:
        try:
            total = int(cr.rsplit("/", 1)[1])
            accept_ranges = True
        except Exception:
            pass

    return total, accept_ranges


def open_session(verify_ssl: bool) -> requests.Session:
    session = requests.Session()
    session.verify = verify_ssl
    return session


def download_stream_single(
    session: requests.Session,
    url: str,
    dest_path: Path,
    headers: dict[str, str],
    timeout: int,
    retries: int,
    resume: bool,
) -> None:
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    # Determine resume position
    resume_pos = 0
    if resume and temp_path.exists():
        resume_pos = temp_path.stat().st_size

    attempt = 0
    while True:
        try:
            req_headers = dict(headers)
            if resume_pos > 0:
                req_headers["Range"] = f"bytes={resume_pos}-"

            with session.get(url, headers=req_headers, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()

                total = resp.headers.get("Content-Length")
                total_int = int(total) + resume_pos if total and total.isdigit() else None

                mode = "ab" if resume_pos > 0 else "wb"
                with open(temp_path, mode) as f, tqdm(
                    total=total_int,
                    initial=resume_pos,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=dest_path.name,
                ) as pbar:
                    for chunk in resp.iter_content(chunk_size=DEFAULT_STREAM_CHUNK_BYTES):
                        if not chunk:
                            continue
                        f.write(chunk)
                        pbar.update(len(chunk))

            temp_path.replace(dest_path)
            return
        except requests.RequestException as e:
            attempt += 1
            if attempt > retries:
                raise DownloadError(f"Failed to download after {retries} retries: {e}")
            backoff_sleep(attempt)


def download_range_to_file(
    session: requests.Session,
    url: str,
    start: int,
    end: int,
    dest_path: Path,
    headers: dict[str, str],
    timeout: int,
    retries: int,
    pbar: tqdm,
) -> None:
    # end is inclusive
    attempt = 0
    while True:
        try:
            range_headers = dict(headers)
            range_headers["Range"] = f"bytes={start}-{end}"
            with session.get(url, headers=range_headers, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                offset = start
                with open(dest_path, "r+b") as f:
                    f.seek(start)
                    for chunk in resp.iter_content(chunk_size=DEFAULT_STREAM_CHUNK_BYTES):
                        if not chunk:
                            continue
                        f.write(chunk)
                        offset += len(chunk)
                        pbar.update(len(chunk))
            return
        except requests.RequestException:
            attempt += 1
            if attempt > retries:
                raise
            backoff_sleep(attempt)


def split_ranges(total: int, connections: int, min_chunk_size: int) -> list[tuple[int, int]]:
    # Inclusive ranges covering [0, total-1]
    connections = max(1, connections)
    approx = max(min_chunk_size, math.ceil(total / connections))
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < total:
        end = min(total - 1, start + approx - 1)
        ranges.append((start, end))
        start = end + 1
    return ranges


def derive_output_filename(url: str, resp: Response | None) -> str:
    # Prefer Content-Disposition
    if resp is not None:
        cd = resp.headers.get("Content-Disposition")
        name = filename_from_content_disposition(cd)
        if name:
            return sanitize_filename(name)
    # Fallback to URL
    return sanitize_filename(guess_filename_from_url(url))


def download_url(
    url: str,
    output_dir: Path,
    connections: int,
    chunk_size: int,
    retries: int,
    timeout: int,
    headers: dict[str, str],
    resume: bool,
    verify_ssl: bool,
) -> Path:
    ensure_dir(output_dir)

    with open_session(verify_ssl=verify_ssl) as session:
        # Probe server capabilities
        probe_resp = get_head_or_probe(session, url, timeout=timeout, headers=headers)
        total, accept_ranges = get_total_and_range_support(probe_resp)
        filename = derive_output_filename(url, probe_resp)
        dest_path = output_dir / filename

        # If file already complete, skip
        if dest_path.exists() and total is not None and dest_path.stat().st_size == total:
            print(f"Already downloaded: {dest_path}")
            return dest_path

        # Parallel path only if we know total and range is supported
        can_parallel = accept_ranges and total is not None and connections > 1

        if not can_parallel:
            download_stream_single(
                session=session,
                url=url,
                dest_path=dest_path,
                headers=headers,
                timeout=timeout,
                retries=retries,
                resume=resume,
            )
            print(f"Saved to {dest_path}")
            return dest_path

        # Parallel download, no per-chunk resume support
        temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
        # Pre-allocate file to final size
        with open(temp_path, "wb") as f:
            f.truncate(total)

        ranges = split_ranges(total=total, connections=connections, min_chunk_size=chunk_size)

        with tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=dest_path.name,
        ) as pbar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(ranges), connections)) as executor:
                futures = [
                    executor.submit(
                        download_range_to_file,
                        session,
                        url,
                        start,
                        end,
                        temp_path,
                        headers,
                        timeout,
                        retries,
                        pbar,
                    )
                    for (start, end) in ranges
                ]
                for fut in concurrent.futures.as_completed(futures):
                    # Propagate any exception
                    fut.result()

        temp_path.replace(dest_path)
        print(f"Saved to {dest_path}")
        return dest_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="legit-downloader",
        description=(
            "Download files you are authorized to access. This tool does NOT bypass DRM or access controls."
        ),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", action="append", help="URL to download (can be passed multiple times)")
    src.add_argument("--list", dest="list_file", help="Path to a text file with one URL per line")

    parser.add_argument("--out", default=str(Path.cwd() / "downloads"), help="Output directory")
    parser.add_argument("--connections", type=int, default=DEFAULT_CONNECTIONS, help="Parallel connections (>=1)")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE_BYTES,
        help="Approximate per-connection chunk size in bytes for parallel downloads",
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retry attempts per request")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Custom header 'Key: Value' (can be passed multiple times)",
    )
    parser.add_argument("--no-resume", action="store_true", help="Disable resume for single-connection downloads")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Do not verify TLS certificates (not recommended)",
    )

    args = parser.parse_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    headers: dict[str, str] = {}
    for h in args.header:
        key, value = parse_kv_header(h)
        headers[key] = value

    output_dir = Path(args.out)
    connections = max(1, int(args.connections))
    chunk_size = max(1024 * 1024, int(args.chunk_size))  # at least 1 MiB
    retries = max(0, int(args.retries))
    timeout = max(1, int(args.timeout))
    resume = not bool(args.no_resume)
    verify_ssl = not bool(args.insecure)

    urls: list[str] = []
    if args.url:
        urls.extend(args.url)
    if args.list_file:
        with open(args.list_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

    if not urls:
        print("No URLs provided.")
        return 2

    failures: list[tuple[str, str]] = []

    for url in urls:
        try:
            download_url(
                url=url,
                output_dir=output_dir,
                connections=connections,
                chunk_size=chunk_size,
                retries=retries,
                timeout=timeout,
                headers=headers,
                resume=resume,
                verify_ssl=verify_ssl,
            )
        except Exception as e:
            failures.append((url, str(e)))

    if failures:
        print("Some downloads failed:")
        for url, err in failures:
            print(f" - {url}: {err}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())