"""Workspace paths for config, snapshots, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path
    config_path: Path
    data_dir: Path
    reports_dir: Path
    run_state_path: Path
    anomalies_path: Path

    @classmethod
    def from_root(
        cls,
        root: Path,
        *,
        config_name: str = "config.yaml",
        data_dirname: str = "data",
        reports_dirname: str = "reports",
    ) -> Workspace:
        root = root.resolve()
        return cls(
            root=root,
            config_path=root / config_name,
            data_dir=root / data_dirname,
            reports_dir=root / reports_dirname,
            run_state_path=root / data_dirname / ".last_run.json",
            anomalies_path=root / data_dirname / ".anomalies.json",
        )
