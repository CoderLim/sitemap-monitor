"""Load and validate monitor configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_INTERVAL = "1d"
DEFAULT_USER_AGENT = "sitemap-monitor/0.1"
DEFAULT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class SiteConfig:
    id: str
    sitemap_urls: list[str]
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    interval: str
    user_agent: str
    timeout_seconds: int
    sites: list[SiteConfig]

    def enabled_sites(self) -> list[SiteConfig]:
        return [s for s in self.sites if s.enabled]


def _parse_sitemap_urls(item: dict[str, Any], index: int) -> list[str]:
    if "sitemap_urls" in item and item["sitemap_urls"] is not None:
        raw_urls = item["sitemap_urls"]
        if not isinstance(raw_urls, list) or not raw_urls:
            raise ValueError(f"config.sites[{index}].sitemap_urls must be a non-empty list")
        urls: list[str] = []
        for j, url in enumerate(raw_urls):
            if not isinstance(url, str) or not url.strip():
                raise ValueError(
                    f"config.sites[{index}].sitemap_urls[{j}] must be a non-empty string"
                )
            urls.append(url.strip())
        return urls

    sitemap_url = item.get("sitemap_url")
    if isinstance(sitemap_url, str) and sitemap_url.strip():
        return [sitemap_url.strip()]

    raise ValueError(
        f"config.sites[{index}] must set sitemap_url or sitemap_urls"
    )


def load_config(path: Path | str) -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")

    # Product defaults: not user-configurable in the dashboard.
    interval = DEFAULT_INTERVAL
    user_agent = DEFAULT_USER_AGENT
    timeout = DEFAULT_TIMEOUT_SECONDS

    sites_raw = raw.get("sites")
    if not isinstance(sites_raw, list) or not sites_raw:
        raise ValueError("config.sites must be a non-empty list")

    sites: list[SiteConfig] = []
    for i, item in enumerate(sites_raw):
        if not isinstance(item, dict):
            raise ValueError(f"config.sites[{i}] must be a mapping")
        site_id = item.get("id")
        if not isinstance(site_id, str) or not site_id.strip():
            raise ValueError(f"config.sites[{i}].id must be a non-empty string")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"config.sites[{i}].enabled must be a boolean")
        sites.append(
            SiteConfig(
                id=site_id.strip(),
                sitemap_urls=_parse_sitemap_urls(item, i),
                enabled=enabled,
            )
        )

    return AppConfig(
        interval=interval,
        user_agent=user_agent.strip(),
        timeout_seconds=timeout,
        sites=sites,
    )


def config_to_dict(cfg: AppConfig) -> dict[str, Any]:
    sites: list[dict[str, Any]] = []
    for site in cfg.sites:
        item: dict[str, Any] = {"id": site.id, "enabled": site.enabled}
        if len(site.sitemap_urls) == 1:
            item["sitemap_url"] = site.sitemap_urls[0]
        else:
            item["sitemap_urls"] = list(site.sitemap_urls)
        sites.append(item)
    return {
        "sites": sites,
    }


def save_config(path: Path | str, cfg: AppConfig) -> None:
    config_path = Path(path)
    payload = config_to_dict(cfg)
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def app_config_from_sites_payload(
    *,
    sites: list[dict[str, Any]],
) -> AppConfig:
    """Build AppConfig from API-shaped site dicts (sitemap_url or sitemap_urls)."""
    if not isinstance(sites, list) or not sites:
        raise ValueError("config.sites must be a non-empty list")

    parsed_sites: list[SiteConfig] = []
    for i, item in enumerate(sites):
        if not isinstance(item, dict):
            raise ValueError(f"config.sites[{i}] must be a mapping")
        site_id = item.get("id")
        if not isinstance(site_id, str) or not site_id.strip():
            raise ValueError(f"config.sites[{i}].id must be a non-empty string")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"config.sites[{i}].enabled must be a boolean")
        parsed_sites.append(
            SiteConfig(
                id=site_id.strip(),
                sitemap_urls=_parse_sitemap_urls(item, i),
                enabled=enabled,
            )
        )
    return AppConfig(
        interval=DEFAULT_INTERVAL,
        user_agent=DEFAULT_USER_AGENT,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        sites=parsed_sites,
    )
