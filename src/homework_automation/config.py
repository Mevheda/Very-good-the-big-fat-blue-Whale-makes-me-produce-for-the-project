from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the runtime configuration is incomplete or invalid."""


@dataclass(frozen=True)
class Settings:
    config_path: Path
    data_dir: Path
    login_url: str
    base_url: str
    browser_channel: str
    browser_executable: str
    headless: bool
    profile_dir: Path
    timeout_ms: int
    proxy_server: str
    credentials_provider: str
    credentials_path: Path | None
    credentials_section: str
    username_env: str
    password_env: str
    raw: dict[str, Any]


def default_config_path() -> Path:
    env_path = os.environ.get("HOMEWORK_AUTOMATION_CONFIG", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd_candidate = Path.cwd() / "config" / "config.yaml"
    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    repo_candidate = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    if repo_candidate.exists():
        return repo_candidate.resolve()

    return cwd_candidate.resolve()


def _resolve_path(value: str | os.PathLike[str], base: Path) -> Path:
    path = Path(os.path.expandvars(str(value))).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path).expanduser().resolve() if config_path else default_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. "
            "Start the chat-led onboarding flow described in "
            "skills/homework-runner/references/onboarding.md."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("The top level of config.yaml must be a mapping.")

    app = raw.get("app", {})
    browser = raw.get("browser", {})
    credentials = raw.get("credentials", {})
    site = raw.get("site", {})

    data_dir = _resolve_path(app.get("data_dir", "../data"), path.parent)
    login_url = str(site.get("login_url", "")).strip()
    base_url = str(site.get("base_url", "")).strip().rstrip("/")
    if not login_url and not base_url:
        raise ConfigError("Set site.login_url or site.base_url in config.yaml.")
    if not login_url:
        login_url = f"{base_url}/login/index.php"
    if not base_url:
        base_url = login_url.split("/login/", 1)[0]

    profile_value = str(browser.get("profile_dir", "browser_profile")).strip()
    profile_dir = _resolve_path(profile_value, data_dir)
    provider = str(credentials.get("provider", "env")).strip().lower()
    credential_path_value = str(credentials.get("path", "credentials.ini")).strip()
    credential_path = _resolve_path(credential_path_value, data_dir) if provider == "file" else None

    return Settings(
        config_path=path,
        data_dir=data_dir,
        login_url=login_url,
        base_url=base_url,
        browser_channel=str(browser.get("channel", "chromium")).strip(),
        browser_executable=str(browser.get("executable_path", "")).strip(),
        headless=bool(browser.get("headless", True)),
        profile_dir=profile_dir,
        timeout_ms=int(browser.get("timeout_seconds", 30)) * 1000,
        proxy_server=str(browser.get("proxy", "")).strip(),
        credentials_provider=provider,
        credentials_path=credential_path,
        credentials_section=str(credentials.get("section", "moodle")).strip(),
        username_env=str(credentials.get("username_env", "HOMEWORK_USERNAME")).strip(),
        password_env=str(credentials.get("password_env", "HOMEWORK_PASSWORD")).strip(),
        raw=raw,
    )


def load_credentials(settings: Settings) -> tuple[str, str]:
    if settings.credentials_provider == "env":
        username = os.environ.get(settings.username_env, "").strip()
        password = os.environ.get(settings.password_env, "").strip()
        if not username or not password:
            raise ConfigError(
                f"Environment variables {settings.username_env} and {settings.password_env} must be set."
            )
        return username, password

    if settings.credentials_provider != "file":
        raise ConfigError("credentials.provider must be `env` or `file`.")
    if settings.credentials_path is None or not settings.credentials_path.exists():
        raise FileNotFoundError(f"Credential file not found: {settings.credentials_path}")

    parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
    parser.read(settings.credentials_path, encoding="utf-8")
    if not parser.has_section(settings.credentials_section):
        raise ConfigError(
            f"Credential file does not contain section [{settings.credentials_section}]."
        )
    username = parser.get(settings.credentials_section, "username", fallback="").strip()
    password = parser.get(settings.credentials_section, "password", fallback="").strip()
    if not username or not password:
        raise ConfigError("Credential username or password is empty.")
    return username, password


def get_course(settings: Settings, course_key: str) -> dict[str, Any]:
    courses = settings.raw.get("courses", {})
    if course_key in courses:
        return courses[course_key]

    normalized = course_key.strip().casefold()
    for key, course in courses.items():
        aliases = [str(alias).casefold() for alias in course.get("aliases", [])]
        if normalized == str(key).casefold() or normalized in aliases:
            return course
    raise ConfigError(f"Unknown course: {course_key}")


def get_assignment(course: dict[str, Any], chapter: int) -> dict[str, Any]:
    assignments = course.get("assignments", {})
    key = str(chapter)
    if key not in assignments:
        raise ConfigError(f"Course has no assignment mapping for chapter {chapter}.")
    return assignments[key]


def assignment_dir(settings: Settings, course_key: str, chapter: int) -> Path:
    return settings.data_dir / "assignments" / course_key / f"chapter-{chapter:02d}"
