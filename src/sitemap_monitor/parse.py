"""Parse sitemap XML / plain-text URL lists into location lists."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class SitemapParseResult:
    kind: str  # "urlset" | "sitemapindex"
    locs: list[str]


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_sitemap(text: str) -> SitemapParseResult:
    """Parse XML sitemaps or newline-delimited text sitemaps (e.g. ``sitemap.txt``)."""
    stripped = text.lstrip()
    if not stripped.startswith("<"):
        return parse_sitemap_text(text)
    return parse_sitemap_xml(text)


def parse_sitemap_text(text: str) -> SitemapParseResult:
    """Parse a plain-text sitemap: one absolute URL per line (``#`` comments allowed)."""
    locs: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            locs.append(line)
    if not locs:
        raise ValueError("empty or unsupported text sitemap")
    return SitemapParseResult(kind="urlset", locs=locs)


def parse_sitemap_xml(xml_text: str) -> SitemapParseResult:
    """Parse a sitemap urlset or sitemapindex document.

    Only collects ``<loc>`` under ``<url>`` / ``<sitemap>``, ignoring nested
    tags such as ``image:loc``.
    """
    root = ET.fromstring(xml_text)
    kind = _local_name(root.tag).lower()
    if kind not in {"urlset", "sitemapindex"}:
        raise ValueError(f"unsupported sitemap root element: {kind}")

    parent_name = "url" if kind == "urlset" else "sitemap"
    locs: list[str] = []
    for parent in root:
        if _local_name(parent.tag).lower() != parent_name:
            continue
        for child in parent:
            if _local_name(child.tag).lower() != "loc":
                continue
            if child.text and child.text.strip():
                locs.append(child.text.strip())
    return SitemapParseResult(kind=kind, locs=locs)
