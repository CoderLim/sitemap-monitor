"""CLI entrypoint for sitemap-monitor."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sitemap_monitor.config import load_config
from sitemap_monitor.diff import DiffResult, diff_snapshots
from sitemap_monitor.fetch import HttpxTextClient, TextClient, collect_urls_from_many
from sitemap_monitor.keywords import extract_keywords_from_url
from sitemap_monitor.report import format_terminal_summary, write_reports
from sitemap_monitor.services.runner_state import RunStatus, save_run_status, utc_now_iso
from sitemap_monitor.services.workspace import Workspace
from sitemap_monitor.store import Snapshot, UrlEntry, load_snapshot, save_snapshot


@dataclass(frozen=True)
class SiteRunResult:
    site_id: str
    is_baseline: bool
    new_urls: list[UrlEntry]
    new_keywords: list[str]
    error: str | None


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    site_results: list[SiteRunResult]


def _repo_root() -> Path:
    return Path.cwd()


def run_monitor(
    *,
    config_path: Path,
    data_dir: Path,
    reports_dir: Path,
    client: TextClient | None = None,
    now: datetime | None = None,
    quiet: bool = False,
) -> RunResult:
    cfg = load_config(config_path)
    http_client = client or HttpxTextClient(
        user_agent=cfg.user_agent,
        timeout_seconds=cfg.timeout_seconds,
    )
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    fetched_at = (now or datetime.now(timezone.utc)).isoformat()

    site_results: list[SiteRunResult] = []
    had_error = False

    for site in cfg.enabled_sites():
        try:
            urls = collect_urls_from_many(site.sitemap_urls, http_client)
            url_entries = [
                UrlEntry(url=url, keywords=extract_keywords_from_url(url))
                for url in urls
            ]
            previous = load_snapshot(data_dir, site.id)
            current = Snapshot(
                site_id=site.id,
                fetched_at=fetched_at,
                baseline=previous is None,
                urls=url_entries,
            )
            diff = diff_snapshots(previous, current)
            save_snapshot(data_dir, current)
            write_reports(
                reports_dir=reports_dir,
                site_id=site.id,
                date_stamp=stamp,
                diff=diff,
                error=None,
            )
            result = SiteRunResult(
                site_id=site.id,
                is_baseline=diff.is_baseline,
                new_urls=list(diff.new_urls),
                new_keywords=list(diff.new_keywords),
                error=None,
            )
        except Exception as exc:  # noqa: BLE001 - per-site isolation
            had_error = True
            empty = DiffResult(is_baseline=False, new_urls=[], new_keywords=[])
            write_reports(
                reports_dir=reports_dir,
                site_id=site.id,
                date_stamp=stamp,
                diff=empty,
                error=str(exc),
            )
            result = SiteRunResult(
                site_id=site.id,
                is_baseline=False,
                new_urls=[],
                new_keywords=[],
                error=str(exc),
            )

        if not quiet:
            print(
                format_terminal_summary(
                    result.site_id,
                    is_baseline=result.is_baseline,
                    new_url_count=len(result.new_urls),
                    new_keywords=result.new_keywords,
                    error=result.error,
                )
            )
        site_results.append(result)

    # Auto-record anomalies after every fetch (no separate manual/live probe).
    try:
        from sitemap_monitor.services.anomalies import collect_anomalies, save_anomalies

        anomalies = collect_anomalies(
            config_path=config_path,
            data_dir=data_dir,
            reports_dir=reports_dir,
            check_sitemaps=False,
            now=now,
        )
        save_anomalies(data_dir / ".anomalies.json", anomalies)
    except Exception:  # noqa: BLE001 - anomaly recording must never break a run
        pass

    return RunResult(exit_code=1 if had_error else 0, site_results=site_results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sitemap-monitor",
        description="Monitor sitemaps and extract new keywords from URL slugs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Fetch sitemaps once and diff against snapshots")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: ./config.yaml)",
    )
    run_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory for per-site snapshots (default: ./data)",
    )
    run_parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory for Markdown/JSON reports (default: ./reports)",
    )

    dash = sub.add_parser("dashboard", help="Start local dashboard API + UI")
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", type=int, default=8787)
    dash.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root containing config.yaml / data / reports",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = _repo_root()

    if args.command == "run":
        config_path = args.config if args.config.is_absolute() else root / args.config
        data_dir = args.data_dir if args.data_dir.is_absolute() else root / args.data_dir
        reports_dir = (
            args.reports_dir if args.reports_dir.is_absolute() else root / args.reports_dir
        )
        started = utc_now_iso()
        save_run_status(
            data_dir / ".last_run.json",
            RunStatus(status="running", started_at=started),
        )
        result = run_monitor(
            config_path=config_path,
            data_dir=data_dir,
            reports_dir=reports_dir,
        )
        save_run_status(
            data_dir / ".last_run.json",
            RunStatus(
                status="completed" if result.exit_code == 0 else "failed",
                started_at=started,
                finished_at=utc_now_iso(),
                exit_code=result.exit_code,
                message="Monitor run finished",
                site_results=[
                    {
                        "site_id": s.site_id,
                        "is_baseline": s.is_baseline,
                        "new_url_count": len(s.new_urls),
                        "new_keyword_count": len(s.new_keywords),
                        "new_keywords": s.new_keywords,
                        "error": s.error,
                    }
                    for s in result.site_results
                ],
            ),
        )
        return result.exit_code

    if args.command == "dashboard":
        import uvicorn

        from sitemap_monitor.api.app import create_app

        ws_root = args.root if args.root.is_absolute() else root / args.root
        app = create_app(Workspace.from_root(ws_root))
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
