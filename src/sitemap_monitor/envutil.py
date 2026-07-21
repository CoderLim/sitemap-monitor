"""Load shared secrets — prefer process env, then sibling link-master/.env.local."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path.cwd().resolve()


def link_master_env_path(root: Path | None = None) -> Path:
    base = root or project_root()
    return base.parent / "link-master" / ".env.local"


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def load_shared_env(*, root: Path | None = None, override: bool = False) -> Path | None:
    """Load link-master env into os.environ when keys are missing.

    Returns the path loaded, or None if not found.
    """
    path = link_master_env_path(root)
    data = parse_dotenv(path)
    if not data:
        return None
    for key, value in data.items():
        if override or key not in os.environ or not str(os.environ.get(key, "")).strip():
            os.environ[key] = value
    return path


def dashboard_access_token() -> str:
    """Token used to protect /api — same role as link-master ACCESS_PASSWORD.

    Precedence: DASHBOARD_TOKEN > ACCESS_PASSWORD.
    """
    for key in ("DASHBOARD_TOKEN", "ACCESS_PASSWORD"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""
