"""Tests for keyword repair against stored snapshots/reports."""

import json
from pathlib import Path

from sitemap_monitor.services.repair_keywords import repair_all


def test_repair_rewrites_snapshot_and_report_phrases(tmp_path: Path):
    data = tmp_path / "data"
    reports = tmp_path / "reports"
    data.mkdir()
    reports.mkdir()

    (data / "gamepix.json").write_text(
        json.dumps(
            {
                "site_id": "gamepix",
                "fetched_at": "2026-07-21T00:00:00+00:00",
                "baseline": False,
                "urls": [
                    {
                        "url": "https://www.gamepix.com/play/dangerous-danny",
                        "keywords": ["dangerous", "danny"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (reports / "2026-07-21-gamepix.json").write_text(
        json.dumps(
            {
                "site_id": "gamepix",
                "date": "2026-07-21",
                "error": None,
                "is_baseline": False,
                "new_urls": [
                    {
                        "url": "https://www.gamepix.com/play/dangerous-danny",
                        "keywords": ["dangerous", "danny"],
                    }
                ],
                "new_keywords": ["danny"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    snap_n, report_n = repair_all(root=tmp_path)
    assert snap_n == 1
    assert report_n == 1

    snap = json.loads((data / "gamepix.json").read_text(encoding="utf-8"))
    assert snap["urls"][0]["keywords"] == ["dangerous danny"]

    report = json.loads((reports / "2026-07-21-gamepix.json").read_text(encoding="utf-8"))
    assert report["new_urls"][0]["keywords"] == ["dangerous danny"]
    assert report["new_keywords"] == ["dangerous danny"]
    assert (reports / "2026-07-21-gamepix.md").exists()
