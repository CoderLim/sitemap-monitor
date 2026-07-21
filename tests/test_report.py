"""Tests for report generation."""

from pathlib import Path

from sitemap_monitor.diff import DiffResult
from sitemap_monitor.report import write_reports
from sitemap_monitor.store import UrlEntry


def test_write_reports_creates_markdown_and_json(tmp_path: Path):
    diff = DiffResult(
        is_baseline=False,
        new_urls=[
            UrlEntry(url="https://example.com/ai-seo-tips", keywords=["ai", "seo", "tips"])
        ],
        new_keywords=["ai", "seo", "tips"],
    )
    paths = write_reports(
        reports_dir=tmp_path,
        site_id="example",
        date_stamp="2026-07-21",
        diff=diff,
        error=None,
    )
    assert paths.markdown.exists()
    assert paths.json_path.exists()
    md = paths.markdown.read_text(encoding="utf-8")
    assert "example" in md
    assert "ai-seo-tips" in md
    assert "ai" in md
    data = paths.json_path.read_text(encoding="utf-8")
    assert "new_keywords" in data


def test_write_reports_baseline_notes_no_new_items(tmp_path: Path):
    diff = DiffResult(is_baseline=True, new_urls=[], new_keywords=[])
    paths = write_reports(
        reports_dir=tmp_path,
        site_id="example",
        date_stamp="2026-07-21",
        diff=diff,
        error=None,
    )
    md = paths.markdown.read_text(encoding="utf-8")
    assert "baseline" in md.lower()
