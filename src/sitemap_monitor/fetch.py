"""Fetch sitemap documents over HTTP and collect page URLs."""

from __future__ import annotations

import subprocess
from typing import Protocol

import httpx

from sitemap_monitor.parse import parse_sitemap_xml


class TextClient(Protocol):
    def get_text(self, url: str) -> str: ...


class HttpxTextClient:
    """HTTP client with curl fallback for Cloudflare-blocked hosts."""

    def __init__(self, *, user_agent: str, timeout_seconds: int) -> None:
        self._user_agent = user_agent
        self._timeout = timeout_seconds

    def get_text(self, url: str) -> str:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/xml,text/xml,*/*;q=0.8",
        }
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 403:
                return self._curl_get(url)
            response.raise_for_status()
            return response.text

    def _curl_get(self, url: str) -> str:
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "-A",
                self._user_agent,
                "--max-time",
                str(self._timeout),
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "curl failed").strip()
            raise RuntimeError(f"curl fetch failed for {url}: {detail}")
        return result.stdout


def collect_urls(
    sitemap_url: str,
    client: TextClient,
    *,
    _visited: set[str] | None = None,
) -> list[str]:
    """Recursively collect page URLs from a sitemap or sitemap index."""
    visited = _visited if _visited is not None else set()
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)

    parsed = parse_sitemap_xml(client.get_text(sitemap_url))
    if parsed.kind == "urlset":
        return list(parsed.locs)

    urls: list[str] = []
    for child in parsed.locs:
        urls.extend(collect_urls(child, client, _visited=visited))
    return urls


def collect_urls_from_many(sitemap_urls: list[str], client: TextClient) -> list[str]:
    """Collect page URLs from multiple sitemap roots, preserving order and deduping."""
    seen: set[str] = set()
    merged: list[str] = []
    visited: set[str] = set()
    for sitemap_url in sitemap_urls:
        for url in collect_urls(sitemap_url, client, _visited=visited):
            if url in seen:
                continue
            seen.add(url)
            merged.append(url)
    return merged
