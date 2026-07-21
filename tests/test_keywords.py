"""Tests for URL slug keyword extraction."""

from sitemap_monitor.keywords import extract_keywords_from_url


def test_extracts_keywords_from_hyphenated_slug():
    assert extract_keywords_from_url("https://example.com/blog/ai-seo-tips") == [
        "ai",
        "seo",
        "tips",
    ]


def test_extracts_keywords_from_underscore_slug():
    assert extract_keywords_from_url("https://example.com/posts/machine_learning_basics") == [
        "machine",
        "learning",
        "basics",
    ]


def test_strips_html_extension():
    assert extract_keywords_from_url("https://example.com/guide/foo-bar.html") == [
        "foo",
        "bar",
    ]


def test_url_decodes_percent_encoding():
    assert extract_keywords_from_url("https://example.com/zh/%E4%B8%AD%E6%96%87-seo") == [
        "中文",
        "seo",
    ]


def test_ignores_root_and_empty_segments():
    assert extract_keywords_from_url("https://example.com/") == []
    assert extract_keywords_from_url("https://example.com") == []


def test_uses_last_path_segment_only():
    assert extract_keywords_from_url("https://example.com/a/b/cool-feature") == [
        "cool",
        "feature",
    ]


def test_filters_numeric_only_and_short_tokens():
    assert extract_keywords_from_url("https://example.com/post/a-12-hello") == ["hello"]
