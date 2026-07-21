"""Tests for sitemap fetching with index recursion."""

from sitemap_monitor.fetch import collect_urls


class FakeClient:
    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls: list[str] = []

    def get_text(self, url: str) -> str:
        self.calls.append(url)
        if url not in self.responses:
            raise RuntimeError(f"unexpected url: {url}")
        return self.responses[url]


def test_collect_urls_follows_sitemap_index():
    index = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/posts.xml</loc></sitemap>
      <sitemap><loc>https://example.com/pages.xml</loc></sitemap>
    </sitemapindex>
    """
    posts = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/blog/one</loc></url>
    </urlset>
    """
    pages = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/about</loc></url>
    </urlset>
    """
    client = FakeClient(
        {
            "https://example.com/sitemap.xml": index,
            "https://example.com/posts.xml": posts,
            "https://example.com/pages.xml": pages,
        }
    )
    urls = collect_urls("https://example.com/sitemap.xml", client)
    assert urls == [
        "https://example.com/blog/one",
        "https://example.com/about",
    ]
    assert client.calls == [
        "https://example.com/sitemap.xml",
        "https://example.com/posts.xml",
        "https://example.com/pages.xml",
    ]


def test_collect_urls_from_urlset_directly():
    urlset = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
    </urlset>
    """
    client = FakeClient({"https://example.com/sitemap.xml": urlset})
    assert collect_urls("https://example.com/sitemap.xml", client) == [
        "https://example.com/a"
    ]


def test_collect_urls_from_many_merges_and_dedupes():
    from sitemap_monitor.fetch import collect_urls_from_many

    a = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://example.com/shared</loc></url>
    </urlset>
    """
    b = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/b</loc></url>
      <url><loc>https://example.com/shared</loc></url>
    </urlset>
    """
    client = FakeClient(
        {
            "https://example.com/1.xml": a,
            "https://example.com/2.xml": b,
        }
    )
    assert collect_urls_from_many(
        [
            "https://example.com/1.xml",
            "https://example.com/2.xml",
        ],
        client,
    ) == [
        "https://example.com/a",
        "https://example.com/shared",
        "https://example.com/b",
    ]
