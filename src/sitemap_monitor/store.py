"""Persist and load per-site sitemap snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class UrlEntry:
    url: str
    keywords: list[str]


@dataclass(frozen=True)
class Snapshot:
    site_id: str
    fetched_at: str
    baseline: bool
    urls: list[UrlEntry]


def snapshot_path(data_dir: Path, site_id: str) -> Path:
    return data_dir / f"{site_id}.json"


def save_snapshot(data_dir: Path, snapshot: Snapshot) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(data_dir, snapshot.site_id)
    payload = {
        "site_id": snapshot.site_id,
        "fetched_at": snapshot.fetched_at,
        "baseline": snapshot.baseline,
        "urls": [asdict(u) for u in snapshot.urls],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_snapshot(data_dir: Path, site_id: str) -> Snapshot | None:
    path = snapshot_path(data_dir, site_id)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    urls = [
        UrlEntry(url=item["url"], keywords=list(item.get("keywords", [])))
        for item in raw.get("urls", [])
    ]
    return Snapshot(
        site_id=raw["site_id"],
        fetched_at=raw["fetched_at"],
        baseline=bool(raw.get("baseline", False)),
        urls=urls,
    )
