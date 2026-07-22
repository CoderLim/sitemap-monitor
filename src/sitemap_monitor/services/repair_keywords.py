"""One-shot repair: re-extract phrase keywords from stored URLs."""

from __future__ import annotations

import json
from pathlib import Path

from sitemap_monitor.diff import DiffResult
from sitemap_monitor.keywords import extract_keywords_from_url
from sitemap_monitor.report import write_reports
from sitemap_monitor.store import Snapshot, UrlEntry, load_snapshot, save_snapshot


def repair_snapshots(data_dir: Path) -> int:
    """Rewrite keywords in every ``data/<site>.json`` snapshot. Returns files changed."""
    changed = 0
    for path in sorted(data_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        site_id = path.stem
        snap = load_snapshot(data_dir, site_id)
        if snap is None:
            continue
        new_urls = [
            UrlEntry(url=entry.url, keywords=extract_keywords_from_url(entry.url))
            for entry in snap.urls
        ]
        if [list(u.keywords) for u in new_urls] == [list(u.keywords) for u in snap.urls]:
            continue
        save_snapshot(
            data_dir,
            Snapshot(
                site_id=snap.site_id,
                fetched_at=snap.fetched_at,
                baseline=snap.baseline,
                urls=new_urls,
            ),
        )
        changed += 1
        print(f"snapshot {site_id}: updated ({len(new_urls)} urls)")
    return changed


def repair_reports(reports_dir: Path) -> int:
    """Rewrite keywords in every ``reports/<date>-<site>.json`` (+ matching .md)."""
    changed = 0
    for path in sorted(reports_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        site_id = str(raw.get("site_id") or "")
        date_stamp = str(raw.get("date") or "")
        if not site_id or not date_stamp:
            # Fallback: 2026-07-21-gamepix.json
            stem = path.stem
            date_stamp = stem[:10]
            site_id = stem[11:]
        error = raw.get("error")
        is_baseline = bool(raw.get("is_baseline"))

        rebuilt_urls: list[UrlEntry] = []
        seen: set[str] = set()
        new_keywords: list[str] = []
        for item in raw.get("new_urls") or []:
            url = item["url"]
            keywords = extract_keywords_from_url(url)
            rebuilt_urls.append(UrlEntry(url=url, keywords=keywords))
            for kw in keywords:
                if kw in seen:
                    continue
                seen.add(kw)
                new_keywords.append(kw)

        old_urls = raw.get("new_urls") or []
        old_keywords = list(raw.get("new_keywords") or [])
        new_payload_urls = [{"url": e.url, "keywords": e.keywords} for e in rebuilt_urls]
        if old_urls == new_payload_urls and old_keywords == new_keywords:
            continue

        write_reports(
            reports_dir=reports_dir,
            site_id=site_id,
            date_stamp=date_stamp,
            diff=DiffResult(
                is_baseline=is_baseline,
                new_urls=rebuilt_urls,
                new_keywords=new_keywords,
            ),
            error=error,
        )
        changed += 1
        print(
            f"report {path.name}: keywords "
            f"{len(old_keywords)} -> {len(new_keywords)}"
        )
    return changed


def repair_all(*, root: Path) -> tuple[int, int]:
    data_dir = root / "data"
    reports_dir = root / "reports"
    snap_n = repair_snapshots(data_dir) if data_dir.is_dir() else 0
    report_n = repair_reports(reports_dir) if reports_dir.is_dir() else 0
    return snap_n, report_n
