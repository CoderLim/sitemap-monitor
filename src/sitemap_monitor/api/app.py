"""FastAPI application for the local dashboard API."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sitemap_monitor.cli import RunResult, run_monitor
from sitemap_monitor.config import (
    app_config_from_sites_payload,
    config_to_dict,
    load_config,
    save_config,
)
from sitemap_monitor.envutil import dashboard_access_token, load_shared_env
from sitemap_monitor.services.anomalies import (
    Anomaly,
    clear_anomalies,
    collect_anomalies,
    load_anomalies,
)
from sitemap_monitor.services.reports import list_report_dates, list_reports, load_report
from sitemap_monitor.services.runner_state import (
    RunStatus,
    load_run_status,
    save_run_status,
    utc_now_iso,
)
from sitemap_monitor.services.workspace import Workspace

_run_lock = threading.Lock()


class SiteIn(BaseModel):
    id: str
    enabled: bool = True
    sitemap_url: str | None = None
    sitemap_urls: list[str] | None = None


class SitesUpdate(BaseModel):
    sites: list[SiteIn]


def create_app(workspace: Workspace | None = None) -> FastAPI:
    ws = workspace or Workspace.from_root(Path.cwd())
    load_shared_env(root=ws.root)
    app = FastAPI(title="sitemap-monitor", version="0.1.0")
    app.state.workspace = ws

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        token = dashboard_access_token()
        if not token:
            return
        expected = f"Bearer {token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/api/health")
    def health(_: None = Depends(require_auth)) -> dict[str, str]:
        return {"status": "ok", "mode": "local"}

    @app.get("/api/sites")
    def get_sites(_: None = Depends(require_auth)) -> dict[str, Any]:
        cfg = load_config(ws.config_path)
        return config_to_dict(cfg)

    @app.put("/api/sites")
    def put_sites(body: SitesUpdate, _: None = Depends(require_auth)) -> dict[str, Any]:
        sites_payload: list[dict[str, Any]] = []
        for site in body.sites:
            item: dict[str, Any] = {"id": site.id, "enabled": site.enabled}
            if site.sitemap_urls:
                item["sitemap_urls"] = site.sitemap_urls
            elif site.sitemap_url:
                item["sitemap_url"] = site.sitemap_url
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"site '{site.id}' needs sitemap_url or sitemap_urls",
                )
            sites_payload.append(item)
        cfg = app_config_from_sites_payload(sites=sites_payload)
        save_config(ws.config_path, cfg)
        return config_to_dict(cfg)

    @app.get("/api/reports/dates")
    def report_dates(_: None = Depends(require_auth)) -> dict[str, list[str]]:
        return {"dates": list_report_dates(ws.reports_dir)}

    @app.get("/api/reports")
    def get_reports(
        date: str | None = None,
        site: str | None = None,
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        if date and site:
            payload = load_report(ws.reports_dir, date, site)
            if payload is None:
                raise HTTPException(status_code=404, detail="report not found")
            return payload
        summaries = list_reports(ws.reports_dir, date=date, site_id=site)
        return {
            "reports": [
                {
                    "date": r.date,
                    "site_id": r.site_id,
                    "error": r.error,
                    "is_baseline": r.is_baseline,
                    "new_keyword_count": r.new_keyword_count,
                    "new_url_count": r.new_url_count,
                }
                for r in summaries
            ]
        }

    @app.post("/api/run")
    def trigger_run(_: None = Depends(require_auth)) -> dict[str, Any]:
        if not _run_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="run already in progress")
        status = RunStatus(
            status="running",
            started_at=utc_now_iso(),
            message="Monitor run started",
        )
        save_run_status(ws.run_state_path, status)

        def _job() -> None:
            try:
                result = run_monitor(
                    config_path=ws.config_path,
                    data_dir=ws.data_dir,
                    reports_dir=ws.reports_dir,
                )
                _persist_result(ws, result)
            except Exception as exc:  # noqa: BLE001
                save_run_status(
                    ws.run_state_path,
                    RunStatus(
                        status="failed",
                        started_at=status.started_at,
                        finished_at=utc_now_iso(),
                        exit_code=1,
                        message=str(exc),
                    ),
                )
            finally:
                _run_lock.release()

        threading.Thread(target=_job, daemon=True).start()
        return status.to_dict()

    @app.get("/api/run/status")
    def run_status(_: None = Depends(require_auth)) -> dict[str, Any]:
        return load_run_status(ws.run_state_path).to_dict()

    @app.get("/api/anomalies")
    def anomalies(_: None = Depends(require_auth)) -> dict[str, Any]:
        # Anomalies are auto-recorded after each fetch; the dashboard only reads them.
        stored = load_anomalies(ws.anomalies_path)
        if stored.get("generated_at"):
            return stored
        # Fallback before the first run: compute local (non-network) checks live.
        items = collect_anomalies(
            config_path=ws.config_path,
            data_dir=ws.data_dir,
            reports_dir=ws.reports_dir,
            check_sitemaps=False,
        )
        return {"generated_at": None, "anomalies": [_anomaly_dict(a) for a in items]}

    @app.delete("/api/anomalies")
    def clear_anomaly_log(_: None = Depends(require_auth)) -> dict[str, Any]:
        return clear_anomalies(ws.anomalies_path)

    dist = ws.root / "dashboard" / "dist"
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}")
        def spa(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


def _anomaly_dict(item: Anomaly) -> dict[str, Any]:
    return {
        "severity": item.severity,
        "code": item.code,
        "site_id": item.site_id,
        "message": item.message,
        "details": item.details,
    }


def _persist_result(ws: Workspace, result: RunResult) -> None:
    save_run_status(
        ws.run_state_path,
        RunStatus(
            status="completed" if result.exit_code == 0 else "failed",
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


def get_app() -> FastAPI:
    return create_app()
