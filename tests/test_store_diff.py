"""Tests for snapshot store and diff."""

from pathlib import Path

from sitemap_monitor.diff import diff_snapshots
from sitemap_monitor.store import Snapshot, UrlEntry, load_snapshot, save_snapshot


def test_save_and_load_snapshot(tmp_path: Path):
    snap = Snapshot(
        site_id="example",
        fetched_at="2026-07-21T00:00:00+00:00",
        baseline=True,
        urls=[
            UrlEntry(url="https://example.com/a", keywords=["a"]),
            UrlEntry(url="https://example.com/b-c", keywords=["b", "c"]),
        ],
    )
    path = save_snapshot(tmp_path, snap)
    assert path.name == "example.json"
    loaded = load_snapshot(tmp_path, "example")
    assert loaded is not None
    assert loaded.site_id == "example"
    assert loaded.baseline is True
    assert len(loaded.urls) == 2
    assert loaded.urls[1].keywords == ["b", "c"]


def test_load_missing_snapshot_returns_none(tmp_path: Path):
    assert load_snapshot(tmp_path, "missing") is None


def test_diff_detects_new_urls_and_keywords():
    previous = Snapshot(
        site_id="example",
        fetched_at="2026-07-20T00:00:00+00:00",
        baseline=False,
        urls=[
            UrlEntry(url="https://example.com/old-post", keywords=["old", "post"]),
        ],
    )
    current = Snapshot(
        site_id="example",
        fetched_at="2026-07-21T00:00:00+00:00",
        baseline=False,
        urls=[
            UrlEntry(url="https://example.com/old-post", keywords=["old", "post"]),
            UrlEntry(url="https://example.com/ai-seo-tips", keywords=["ai", "seo", "tips"]),
        ],
    )
    result = diff_snapshots(previous, current)
    assert result.is_baseline is False
    assert [e.url for e in result.new_urls] == ["https://example.com/ai-seo-tips"]
    assert result.new_keywords == ["ai", "seo", "tips"]


def test_diff_first_run_is_baseline():
    current = Snapshot(
        site_id="example",
        fetched_at="2026-07-21T00:00:00+00:00",
        baseline=True,
        urls=[UrlEntry(url="https://example.com/a", keywords=["a"])],
    )
    result = diff_snapshots(None, current)
    assert result.is_baseline is True
    assert result.new_urls == []
    assert result.new_keywords == []


def test_diff_keywords_only_counts_first_appearance():
    previous = Snapshot(
        site_id="example",
        fetched_at="2026-07-20T00:00:00+00:00",
        baseline=False,
        urls=[UrlEntry(url="https://example.com/ai-guide", keywords=["ai", "guide"])],
    )
    current = Snapshot(
        site_id="example",
        fetched_at="2026-07-21T00:00:00+00:00",
        baseline=False,
        urls=[
            UrlEntry(url="https://example.com/ai-guide", keywords=["ai", "guide"]),
            UrlEntry(url="https://example.com/ai-seo", keywords=["ai", "seo"]),
        ],
    )
    result = diff_snapshots(previous, current)
    assert result.new_keywords == ["seo"]
