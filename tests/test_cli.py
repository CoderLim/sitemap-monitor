"""Tests for CLI run orchestration."""

from pathlib import Path

from sitemap_monitor.cli import run_monitor


INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/blog/old-post</loc></url>
  <url><loc>https://example.com/blog/ai-seo-tips</loc></url>
</urlset>
"""

BASELINE = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/blog/old-post</loc></url>
</urlset>
"""


class FakeClient:
    def __init__(self, text: str):
        self.text = text

    def get_text(self, url: str) -> str:
        return self.text


def _write_config(path: Path) -> None:
    path.write_text(
        """
interval: 6h
user_agent: "test-agent"
timeout_seconds: 10
sites:
  - id: example
    sitemap_url: https://example.com/sitemap.xml
    enabled: true
""",
        encoding="utf-8",
    )


def test_run_monitor_baseline_then_detects_new(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    _write_config(config_path)

    first = run_monitor(
        config_path=config_path,
        data_dir=data_dir,
        reports_dir=reports_dir,
        client=FakeClient(BASELINE),
    )
    assert first.exit_code == 0
    assert first.site_results[0].is_baseline is True
    assert first.site_results[0].new_keywords == []

    second = run_monitor(
        config_path=config_path,
        data_dir=data_dir,
        reports_dir=reports_dir,
        client=FakeClient(INDEX),
    )
    assert second.exit_code == 0
    assert second.site_results[0].is_baseline is False
    assert "ai" in second.site_results[0].new_keywords
    assert any(reports_dir.glob("*-example.md"))


def test_run_monitor_continues_after_site_failure(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval: 1h
sites:
  - id: bad
    sitemap_url: https://bad.example/sitemap.xml
    enabled: true
  - id: good
    sitemap_url: https://example.com/sitemap.xml
    enabled: true
""",
        encoding="utf-8",
    )

    class MixedClient:
        def get_text(self, url: str) -> str:
            if "bad" in url:
                raise RuntimeError("boom")
            return BASELINE

    result = run_monitor(
        config_path=config_path,
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        client=MixedClient(),
    )
    assert result.exit_code == 1
    assert result.site_results[0].error is not None
    assert result.site_results[1].is_baseline is True
