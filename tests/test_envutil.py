"""Tests for shared env / dashboard token resolution."""

import os
from pathlib import Path

from sitemap_monitor.envutil import dashboard_access_token, load_shared_env, parse_dotenv


def test_parse_dotenv(tmp_path: Path):
    path = tmp_path / ".env.local"
    path.write_text('ACCESS_PASSWORD="secret"\nGITHUB_TOKEN=abc\n', encoding="utf-8")
    assert parse_dotenv(path)["ACCESS_PASSWORD"] == "secret"
    assert parse_dotenv(path)["GITHUB_TOKEN"] == "abc"


def test_dashboard_token_prefers_dashboard_over_access(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "dash")
    monkeypatch.setenv("ACCESS_PASSWORD", "access")
    assert dashboard_access_token() == "dash"


def test_dashboard_token_falls_back_to_access_password(monkeypatch):
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setenv("ACCESS_PASSWORD", "access")
    assert dashboard_access_token() == "access"


def test_load_shared_env_from_sibling(tmp_path: Path, monkeypatch):
    root = tmp_path / "sitemap-monitor"
    sibling = tmp_path / "link-master"
    root.mkdir()
    sibling.mkdir()
    (sibling / ".env.local").write_text("ACCESS_PASSWORD=from-sibling\n", encoding="utf-8")
    monkeypatch.delenv("ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    loaded = load_shared_env(root=root)
    assert loaded is not None
    assert os.environ["ACCESS_PASSWORD"] == "from-sibling"
    assert dashboard_access_token() == "from-sibling"
    monkeypatch.delenv("ACCESS_PASSWORD", raising=False)
