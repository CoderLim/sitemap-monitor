"""Detect operational anomalies for the dashboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sitemap_monitor.config import AppConfig, load_config
from sitemap_monitor.fetch import HttpxTextClient, TextClient
from sitemap_monitor.interval import interval_to_seconds
from sitemap_monitor.parse import parse_sitemap_xml
from sitemap_monitor.services.reports import latest_reports_by_site
from sitemap_monitor.store import load_snapshot

WARN_BYTES = 5 * 1024 * 1024
CRITICAL_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Anomaly:
    severity: str  # info | warning | critical
    code: str
    site_id: str | None
    message: str
    details: dict[str, Any] | None = None


def anomaly_to_dict(item: Anomaly) -> dict[str, Any]:
    return asdict(item)


def save_anomalies(path: Path, items: list[Anomaly], *, generated_at: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "generated_at": ts,
        "anomalies": [{**anomaly_to_dict(a), "recorded_at": ts} for a in items],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_anomalies(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "anomalies": []}
    return json.loads(path.read_text(encoding="utf-8"))


def clear_anomalies(path: Path) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload: dict[str, Any] = {"generated_at": ts, "anomalies": []}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def collect_anomalies(
    *,
    config_path: Path,
    data_dir: Path,
    reports_dir: Path,
    client: TextClient | None = None,
    check_sitemaps: bool = False,
    now: datetime | None = None,
) -> list[Anomaly]:
    cfg = load_config(config_path)
    now = now or datetime.now(timezone.utc)
    anomalies: list[Anomaly] = []

    anomalies.extend(_snapshot_anomalies(cfg, data_dir, now))
    anomalies.extend(_report_error_anomalies(reports_dir))
    if check_sitemaps:
        http = client or HttpxTextClient(
            user_agent=cfg.user_agent,
            timeout_seconds=min(cfg.timeout_seconds, 30),
        )
        anomalies.extend(_sitemap_probe_anomalies(cfg, http))
    return anomalies


def _snapshot_anomalies(cfg: AppConfig, data_dir: Path, now: datetime) -> list[Anomaly]:
    items: list[Anomaly] = []
    stale_after = interval_to_seconds(cfg.interval) * 2
    for site in cfg.enabled_sites():
        path = data_dir / f"{site.id}.json"
        if not path.exists():
            items.append(
                Anomaly(
                    severity="warning",
                    code="missing_snapshot",
                    site_id=site.id,
                    message=f"Enabled site '{site.id}' has no data/{site.id}.json snapshot yet",
                )
            )
            continue

        size = path.stat().st_size
        if size >= CRITICAL_BYTES:
            items.append(
                Anomaly(
                    severity="critical",
                    code="snapshot_too_large",
                    site_id=site.id,
                    message=f"Snapshot {path.name} is {size / (1024 * 1024):.1f} MB (limit 10 MB)",
                    details={"bytes": size, "path": str(path)},
                )
            )
        elif size >= WARN_BYTES:
            items.append(
                Anomaly(
                    severity="warning",
                    code="snapshot_large",
                    site_id=site.id,
                    message=f"Snapshot {path.name} is {size / (1024 * 1024):.1f} MB (warn at 5 MB)",
                    details={"bytes": size, "path": str(path)},
                )
            )

        snap = load_snapshot(data_dir, site.id)
        if snap is None:
            continue
        if not snap.urls:
            items.append(
                Anomaly(
                    severity="critical",
                    code="empty_snapshot",
                    site_id=site.id,
                    message=(
                        f"Latest fetch for '{site.id}' returned 0 URLs "
                        "(sitemap may be empty or blocked)"
                    ),
                    details={"fetched_at": snap.fetched_at},
                )
            )
        try:
            fetched = datetime.fromisoformat(snap.fetched_at)
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
        except ValueError:
            items.append(
                Anomaly(
                    severity="warning",
                    code="invalid_fetched_at",
                    site_id=site.id,
                    message=f"Snapshot for '{site.id}' has invalid fetched_at",
                )
            )
            continue
        age = (now - fetched).total_seconds()
        if age > stale_after:
            items.append(
                Anomaly(
                    severity="warning",
                    code="snapshot_stale",
                    site_id=site.id,
                    message=(
                        f"Snapshot for '{site.id}' is stale "
                        f"({int(age // 3600)}h old; interval={cfg.interval})"
                    ),
                    details={"fetched_at": snap.fetched_at, "age_seconds": int(age)},
                )
            )
    return items


def _report_error_anomalies(reports_dir: Path) -> list[Anomaly]:
    items: list[Anomaly] = []
    for site_id, report in latest_reports_by_site(reports_dir).items():
        if report.error:
            items.append(
                Anomaly(
                    severity="critical",
                    code="last_run_error",
                    site_id=site_id,
                    message=f"Latest report for '{site_id}' ({report.date}) has an error",
                    details={"error": report.error, "date": report.date},
                )
            )
    return items


def _sitemap_probe_anomalies(cfg: AppConfig, client: TextClient) -> list[Anomaly]:
    items: list[Anomaly] = []
    for site in cfg.enabled_sites():
        empty_count = 0
        for url in site.sitemap_urls:
            try:
                text = client.get_text(url)
                parsed = parse_sitemap_xml(text)
                if not parsed.locs:
                    empty_count += 1
                    items.append(
                        Anomaly(
                            severity="warning",
                            code="sitemap_empty",
                            site_id=site.id,
                            message=f"Sitemap returned zero locs: {url}",
                            details={"url": url},
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                items.append(
                    Anomaly(
                        severity="critical",
                        code="sitemap_unreachable",
                        site_id=site.id,
                        message=f"Sitemap probe failed: {url}",
                        details={"url": url, "error": str(exc)},
                    )
                )
        if empty_count >= 2 and empty_count == len(site.sitemap_urls):
            items.append(
                Anomaly(
                    severity="critical",
                    code="all_sitemap_shards_empty",
                    site_id=site.id,
                    message=f"All configured sitemap URLs for '{site.id}' are empty",
                )
            )
    return items
