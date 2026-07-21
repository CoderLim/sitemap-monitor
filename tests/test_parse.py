"""Tests for sitemap XML parsing."""

from sitemap_monitor.parse import parse_sitemap_xml


URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/blog/ai-seo-tips</loc></url>
  <url><loc>https://example.com/about</loc></url>
</urlset>
"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-posts.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""


def test_parse_urlset_returns_locs():
    result = parse_sitemap_xml(URLSET)
    assert result.kind == "urlset"
    assert result.locs == [
        "https://example.com/blog/ai-seo-tips",
        "https://example.com/about",
    ]


def test_parse_sitemap_index_returns_child_sitemap_locs():
    result = parse_sitemap_xml(SITEMAP_INDEX)
    assert result.kind == "sitemapindex"
    assert result.locs == [
        "https://example.com/sitemap-posts.xml",
        "https://example.com/sitemap-pages.xml",
    ]


def test_parse_urlset_ignores_image_loc():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
      <url>
        <loc>https://www.gamepix.com/play/tentrix</loc>
        <image:image>
          <image:loc>https://img.gamepix.com/games/tentrix/cover.png</image:loc>
        </image:image>
      </url>
    </urlset>
    """
    result = parse_sitemap_xml(xml)
    assert result.locs == ["https://www.gamepix.com/play/tentrix"]
