"""Write Markdown/JSON reports and format terminal summaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sitemap_monitor.diff import DiffResult


@dataclass(frozen=True)
class ReportPaths:
    markdown: Path
    json_path: Path


def write_reports(
    *,
    reports_dir: Path,
    site_id: str,
    date_stamp: str,
    diff: DiffResult,
    error: str | None,
) -> ReportPaths:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date_stamp}-{site_id}"
    markdown_path = reports_dir / f"{stem}.md"
    json_path = reports_dir / f"{stem}.json"

    lines = [
        f"# Sitemap monitor report: {site_id}",
        "",
        f"- Date: `{date_stamp}`",
    ]
    if error:
        lines.extend(["", "## Error", "", f"```\n{error}\n```"])
    elif diff.is_baseline:
        lines.extend(
            [
                "",
                "## Baseline",
                "",
                "First run for this site. Snapshot saved; no new URLs/keywords reported.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"- New URLs: **{len(diff.new_urls)}**",
                f"- New keywords: **{len(diff.new_keywords)}**",
                "",
                "## New keywords",
                "",
            ]
        )
        if diff.new_keywords:
            lines.extend(f"- `{kw}`" for kw in diff.new_keywords)
        else:
            lines.append("_None_")
        lines.extend(["", "## New URLs", ""])
        if diff.new_urls:
            for entry in diff.new_urls:
                kw = ", ".join(entry.keywords) if entry.keywords else "(none)"
                lines.append(f"- {entry.url} — `{kw}`")
        else:
            lines.append("_None_")

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "site_id": site_id,
        "date": date_stamp,
        "error": error,
        "is_baseline": diff.is_baseline,
        "new_urls": [
            {"url": e.url, "keywords": e.keywords} for e in diff.new_urls
        ],
        "new_keywords": list(diff.new_keywords),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return ReportPaths(markdown=markdown_path, json_path=json_path)


def format_terminal_summary(
    site_id: str,
    *,
    is_baseline: bool,
    new_url_count: int,
    new_keywords: list[str],
    error: str | None,
) -> str:
    if error:
        return f"[{site_id}] ERROR: {error}"
    if is_baseline:
        return f"[{site_id}] baseline established (no new items reported)"
    keywords = ", ".join(new_keywords) if new_keywords else "(none)"
    return (
        f"[{site_id}] new_urls={new_url_count} "
        f"new_keywords={len(new_keywords)} [{keywords}]"
    )
