"""Extract keywords from URL path slugs."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_EXTENSIONS = {".html", ".htm", ".php", ".aspx", ".jsp", ".xml"}
_SPLIT_RE = re.compile(r"[-_]+")


def extract_keywords_from_url(url: str) -> list[str]:
    """Return keyword tokens from the last non-empty path segment of *url*."""
    path = unquote(urlparse(url).path or "")
    segments = [s for s in path.split("/") if s]
    if not segments:
        return []

    slug = segments[-1].lower()
    for ext in _EXTENSIONS:
        if slug.endswith(ext):
            slug = slug[: -len(ext)]
            break

    tokens: list[str] = []
    for token in _SPLIT_RE.split(slug):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            continue
        if len(token) < 2:
            continue
        tokens.append(token)
    return tokens
