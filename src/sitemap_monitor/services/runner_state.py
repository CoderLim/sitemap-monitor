"""Persist and read last monitor run status for the dashboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunStatus:
    status: str  # idle | running | completed | failed | queued
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    message: str | None = None
    site_results: list[dict[str, Any]] | None = None
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_run_status(path: Path) -> RunStatus:
    if not path.exists():
        return RunStatus(status="idle")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RunStatus(
        status=raw.get("status", "idle"),
        started_at=raw.get("started_at"),
        finished_at=raw.get("finished_at"),
        exit_code=raw.get("exit_code"),
        message=raw.get("message"),
        site_results=raw.get("site_results"),
        run_id=raw.get("run_id"),
    )


def save_run_status(path: Path, status: RunStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
