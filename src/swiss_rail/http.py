"""Bounded downloads, conditional requests, checksums, and retryable failures."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

RETRYABLE = {429, 500, 502, 503, 504}


def client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(90, connect=20),
        follow_redirects=True,
        headers={"User-Agent": "SwissRailObservatory/0.1 (portfolio data pipeline)"},
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    url: str,
    destination: Path,
    *,
    refresh: bool = False,
    max_bytes: int = 2_000_000_000,
    http: httpx.Client | None = None,
) -> Path:
    """Keep old data intact until a whole, non-empty replacement is downloaded."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destination.with_suffix(destination.suffix + ".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    valid_cache = (
        destination.exists()
        and meta.get("url") == url
        and meta.get("sha256") == sha256(destination)
    )
    if valid_cache and not refresh:
        return destination
    headers = {}
    if valid_cache and meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    own_client = http is None
    http = http or client()
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        for attempt in range(3):
            try:
                with http.stream("GET", url, headers=headers) as response:
                    if response.status_code == 304 and valid_cache:
                        return destination
                    response.raise_for_status()
                    if int(response.headers.get("content-length", "0")) > max_bytes:
                        raise ValueError(f"Download exceeds the {max_bytes:,}-byte limit: {url}")
                    size = 0
                    with partial.open("wb") as file:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise ValueError(f"Download exceeds size limit: {url}")
                            file.write(chunk)
                    if size == 0:
                        raise ValueError(f"Empty source file: {url}")
                    meta = {
                        "url": url,
                        "sha256": sha256(partial),
                        "etag": response.headers.get("etag"),
                        "bytes": size,
                    }
                    partial.replace(destination)
                    meta_path.write_text(json.dumps(meta, indent=2))
                    return destination
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                if isinstance(error, httpx.HTTPStatusError):
                    if error.response.status_code not in RETRYABLE:
                        raise
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("Download did not complete")
    finally:
        partial.unlink(missing_ok=True)
        if own_client:
            http.close()
