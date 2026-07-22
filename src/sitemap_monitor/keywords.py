"""Extract keywords from URL path slugs."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_EXTENSIONS = {".html", ".htm", ".php", ".aspx", ".jsp", ".xml"}
_SEP_RE = re.compile(r"[-_]+")
_SPACE_RE = re.compile(r"\s+")


def extract_keywords_from_url(url: str) -> list[str]:
    """Return the last path slug as one phrase keyword (hyphens/underscores → spaces).

    Example: ``/play/dangerous-danny`` → ``["dangerous danny"]``.
    """
    path = unquote(urlparse(url).path or "")
    segments = [s for s in path.split("/") if s]
    if not segments:
        return []

    slug = segments[-1].lower()
    for ext in _EXTENSIONS:
        if slug.endswith(ext):
            slug = slug[: -len(ext)]
            break

    phrase = _SPACE_RE.sub(" ", _SEP_RE.sub(" ", slug)).strip()
    if not phrase:
        return []
    if phrase.isdigit():
        return []
    if len(phrase) < 2:
        return []
    return [phrase]
