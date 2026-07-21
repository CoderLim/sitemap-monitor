from fastapi.testclient import TestClient

from sitemap_monitor.api.app import create_app
from sitemap_monitor.config import AppConfig, SiteConfig, save_config
from sitemap_monitor.services.workspace import Workspace


def test_api_sites_and_reports(tmp_path, monkeypatch):
    monkeypatch.delenv("ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    root = tmp_path
    (root / "data").mkdir()
    (root / "reports").mkdir()
    save_config(
        root / "config.yaml",
        AppConfig(
            interval="6h",
            user_agent="test",
            timeout_seconds=10,
            sites=[SiteConfig(id="demo", sitemap_urls=["https://example.com/sitemap.xml"])],
        ),
    )
    (root / "reports" / "2026-07-21-demo.json").write_text(
        '{"site_id":"demo","date":"2026-07-21","error":null,"is_baseline":false,'
        '"new_urls":[],"new_keywords":["alpha"]}\n',
        encoding="utf-8",
    )
    app = create_app(Workspace.from_root(root))
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    sites = client.get("/api/sites").json()
    assert sites["sites"][0]["id"] == "demo"
    dates = client.get("/api/reports/dates").json()["dates"]
    assert dates == ["2026-07-21"]
    report = client.get("/api/reports", params={"date": "2026-07-21", "site": "demo"}).json()
    assert report["new_keywords"] == ["alpha"]
    anomalies = client.get("/api/anomalies").json()["anomalies"]
    assert any(a["code"] == "missing_snapshot" for a in anomalies)


def test_api_requires_access_password_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCESS_PASSWORD", "shared-secret")
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    root = tmp_path
    (root / "data").mkdir()
    (root / "reports").mkdir()
    save_config(
        root / "config.yaml",
        AppConfig(
            interval="6h",
            user_agent="test",
            timeout_seconds=10,
            sites=[SiteConfig(id="demo", sitemap_urls=["https://example.com/sitemap.xml"])],
        ),
    )
    app = create_app(Workspace.from_root(root))
    client = TestClient(app)
    assert client.get("/api/health").status_code == 401
    ok = client.get("/api/health", headers={"Authorization": "Bearer shared-secret"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"
