"""Read daily JSON reports from the reports directory."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPORT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.json$")


@dataclass(frozen=True)
class ReportSummary:
    date: str
    site_id: str
    path: Path
    error: str | None
    is_baseline: bool
    new_keyword_count: int
    new_url_count: int


def list_report_dates(reports_dir: Path) -> list[str]:
    dates = {m.group(1) for m in (_match_report(p) for p in _json_reports(reports_dir)) if m}
    return sorted(dates, reverse=True)


def list_reports(
    reports_dir: Path,
    *,
    date: str | None = None,
    site_id: str | None = None,
) -> list[ReportSummary]:
    items: list[ReportSummary] = []
    for path in _json_reports(reports_dir):
        matched = _match_report(path)
        if not matched:
            continue
        report_date, report_site = matched.group(1), matched.group(2)
        if date and report_date != date:
            continue
        if site_id and report_site != site_id:
            continue
        payload = _load_json(path)
        items.append(
            ReportSummary(
                date=report_date,
                site_id=report_site,
                path=path,
                error=payload.get("error"),
                is_baseline=bool(payload.get("is_baseline")),
                new_keyword_count=len(payload.get("new_keywords") or []),
                new_url_count=len(payload.get("new_urls") or []),
            )
        )
    items.sort(key=lambda r: (r.date, r.site_id), reverse=True)
    return items


def load_report(reports_dir: Path, date: str, site_id: str) -> dict[str, Any] | None:
    path = reports_dir / f"{date}-{site_id}.json"
    if not path.exists():
        return None
    return _load_json(path)


def latest_reports_by_site(reports_dir: Path) -> dict[str, ReportSummary]:
    latest: dict[str, ReportSummary] = {}
    for report in list_reports(reports_dir):
        if report.site_id not in latest:
            latest[report.site_id] = report
    return latest


def _json_reports(reports_dir: Path) -> list[Path]:
    if not reports_dir.exists():
        return []
    return sorted(reports_dir.glob("*.json"))


def _match_report(path: Path) -> re.Match[str] | None:
    return _REPORT_NAME.match(path.name)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
