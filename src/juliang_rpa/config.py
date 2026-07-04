from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass(frozen=True)
class BrowserSettings:
    user_data_dir: Path
    headless: bool
    slow_mo_ms: int
    timeout_ms: int
    channel: str
    use_system_chrome: bool
    executable_path: Path | None
    viewport_width: int
    viewport_height: int


@dataclass(frozen=True)
class ArtifactSettings:
    logs_dir: Path
    recordings_dir: Path


@dataclass(frozen=True)
class AppSettings:
    base_url: str
    login_url: str
    create_ad_url_template: str
    browser: BrowserSettings
    artifacts: ArtifactSettings

    def create_ad_url(self, account_id: str) -> str:
        normalized_account_id = account_id.strip()
        if not normalized_account_id:
            raise ValueError("Account ID is required.")
        encoded_account_id = quote(normalized_account_id, safe="")
        return self.create_ad_url_template.format(account_id=encoded_account_id)


def load_settings(config_path: Path | None = None) -> AppSettings:
    load_dotenv(PROJECT_ROOT / ".env")

    path = config_path or DEFAULT_CONFIG_PATH
    raw = _read_yaml(path)
    site = raw.get("site", {})
    browser = raw.get("browser", {})
    viewport = browser.get("viewport", {})
    artifacts = raw.get("artifacts", {})

    base_url = os.getenv("JULIANG_BASE_URL", site.get("base_url", "")).strip()
    if not base_url:
        raise ValueError("Missing JULIANG_BASE_URL or site.base_url.")
    login_url = os.getenv("JULIANG_LOGIN_URL", site.get("login_url", base_url)).strip()
    if not login_url:
        raise ValueError("Missing JULIANG_LOGIN_URL or site.login_url.")
    create_ad_url_template = os.getenv(
        "JULIANG_CREATE_AD_URL_TEMPLATE",
        site.get(
            "create_ad_url_template",
            "https://ad.oceanengine.com/ad/web/std/ad/create?aadvid={account_id}&campaign_type=1",
        ),
    ).strip()
    if "{account_id}" not in create_ad_url_template:
        raise ValueError("create_ad_url_template must contain {account_id}.")

    user_data_dir = _resolve_path(
        os.getenv("JULIANG_USER_DATA_DIR", browser.get("user_data_dir", ".auth/juliang-chrome"))
    )
    logs_dir = _resolve_path(artifacts.get("logs_dir", "logs"))
    recordings_dir = _resolve_path(artifacts.get("recordings_dir", "recordings"))

    return AppSettings(
        base_url=base_url,
        login_url=login_url,
        create_ad_url_template=create_ad_url_template,
        browser=BrowserSettings(
            user_data_dir=user_data_dir,
            headless=_env_bool("JULIANG_HEADLESS", browser.get("headless", False)),
            slow_mo_ms=_env_int("JULIANG_SLOW_MO_MS", browser.get("slow_mo_ms", 80)),
            timeout_ms=_env_int("JULIANG_TIMEOUT_MS", browser.get("timeout_ms", 30000)),
            channel=str(browser.get("channel", "chrome")),
            use_system_chrome=_env_bool(
                "JULIANG_USE_SYSTEM_CHROME",
                browser.get("use_system_chrome", True),
            ),
            executable_path=_optional_path(
                os.getenv("JULIANG_BROWSER_EXECUTABLE", browser.get("executable_path", ""))
            ),
            viewport_width=int(viewport.get("width", 1440)),
            viewport_height=int(viewport.get("height", 960)),
        ),
        artifacts=ArtifactSettings(logs_dir=logs_dir, recordings_dir=recordings_dir),
    )


def ensure_runtime_dirs(settings: AppSettings) -> None:
    settings.browser.user_data_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts.recordings_dir.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def _resolve_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _optional_path(value: str | os.PathLike[str] | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return _resolve_path(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return int(default)
    return int(value)
