"""Compare sitemap snapshots for new URLs and keywords."""

from __future__ import annotations

from dataclasses import dataclass

from sitemap_monitor.store import Snapshot, UrlEntry


@dataclass(frozen=True)
class DiffResult:
    is_baseline: bool
    new_urls: list[UrlEntry]
    new_keywords: list[str]


def diff_snapshots(previous: Snapshot | None, current: Snapshot) -> DiffResult:
    if previous is None:
        return DiffResult(is_baseline=True, new_urls=[], new_keywords=[])

    previous_urls = {entry.url for entry in previous.urls}
    previous_keywords = {
        keyword for entry in previous.urls for keyword in entry.keywords
    }

    new_urls = [entry for entry in current.urls if entry.url not in previous_urls]
    seen: set[str] = set()
    new_keywords: list[str] = []
    for entry in new_urls:
        for keyword in entry.keywords:
            if keyword in previous_keywords or keyword in seen:
                continue
            seen.add(keyword)
            new_keywords.append(keyword)

    return DiffResult(is_baseline=False, new_urls=new_urls, new_keywords=new_keywords)
