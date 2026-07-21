"""Tests for config loading."""

from pathlib import Path

import pytest

from sitemap_monitor.config import load_config


def test_load_config_reads_sites(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
sites:
  - id: example
    sitemap_url: https://example.com/sitemap.xml
    enabled: true
  - id: disabled
    sitemap_url: https://other.com/sitemap.xml
    enabled: false
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.interval == "1d"
    assert cfg.user_agent == "sitemap-monitor/0.1"
    assert cfg.timeout_seconds == 60
    assert len(cfg.sites) == 2
    assert cfg.enabled_sites()[0].id == "example"
    assert cfg.enabled_sites()[0].sitemap_urls == [
        "https://example.com/sitemap.xml"
    ]


def test_load_config_defaults_interval_to_one_day(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
sites:
  - id: example
    sitemap_url: https://example.com/sitemap.xml
    enabled: true
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.interval == "1d"
    assert cfg.timeout_seconds == 60


def test_load_config_accepts_sitemap_urls_list(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
interval: 6h
sites:
  - id: gamepix
    sitemap_urls:
      - https://www.gamepix.com/sitemaps/games-1.xml
      - https://www.gamepix.com/sitemaps/games-2.xml
    enabled: true
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.sites[0].sitemap_urls == [
        "https://www.gamepix.com/sitemaps/games-1.xml",
        "https://www.gamepix.com/sitemaps/games-2.xml",
    ]


def test_load_config_rejects_missing_sites(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("sites: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sites"):
        load_config(path)
