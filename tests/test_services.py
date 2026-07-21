"""Tests for report listing and config save."""

from pathlib import Path

from sitemap_monitor.config import AppConfig, SiteConfig, load_config, save_config
from sitemap_monitor.interval import interval_to_seconds
from sitemap_monitor.services.anomalies import collect_anomalies
from sitemap_monitor.services.reports import list_report_dates, list_reports, load_report


def test_interval_to_seconds():
    assert interval_to_seconds("6h") == 6 * 3600
    assert interval_to_seconds("30m") == 30 * 60


def test_save_and_reload_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    cfg = AppConfig(
        interval="6h",
        user_agent="test",
        timeout_seconds=30,
        sites=[
            SiteConfig(id="a", sitemap_urls=["https://a.com/sitemap.xml"], enabled=True),
            SiteConfig(
                id="b",
                sitemap_urls=[
                    "https://b.com/1.xml",
                    "https://b.com/2.xml",
                ],
                enabled=False,
            ),
        ],
    )
    save_config(path, cfg)
    loaded = load_config(path)
    assert loaded.sites[0].sitemap_urls == ["https://a.com/sitemap.xml"]
    assert loaded.sites[1].sitemap_urls == ["https://b.com/1.xml", "https://b.com/2.xml"]
    assert loaded.sites[1].enabled is False


def test_list_and_load_reports(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "2026-07-21-poki.json").write_text(
        '{"site_id":"poki","date":"2026-07-21","error":null,'
        '"is_baseline":false,"new_urls":[{"url":"https://x","keywords":["x"]}],'
        '"new_keywords":["x","y"]}\n',
        encoding="utf-8",
    )
    (reports / "2026-07-20-poki.json").write_text(
        '{"site_id":"poki","date":"2026-07-20","error":null,'
        '"is_baseline":true,"new_urls":[],"new_keywords":[]}\n',
        encoding="utf-8",
    )
    assert list_report_dates(reports) == ["2026-07-21", "2026-07-20"]
    day = list_reports(reports, date="2026-07-21")
    assert len(day) == 1
    assert day[0].new_keyword_count == 2
    payload = load_report(reports, "2026-07-21", "poki")
    assert payload is not None
    assert payload["new_keywords"] == ["x", "y"]


def test_collect_anomalies_missing_snapshot(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
interval: 1h
sites:
  - id: missing
    sitemap_url: https://example.com/sitemap.xml
    enabled: true
""",
        encoding="utf-8",
    )
    data = tmp_path / "data"
    data.mkdir()
    reports = tmp_path / "reports"
    reports.mkdir()
    items = collect_anomalies(
        config_path=config,
        data_dir=data,
        reports_dir=reports,
        check_sitemaps=False,
    )
    assert any(a.code == "missing_snapshot" for a in items)
