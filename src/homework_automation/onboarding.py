from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, default_config_path


def default_data_dir() -> Path:
    configured = os.environ.get("HOMEWORK_AUTOMATION_DATA", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "HomeworkAutomation").resolve()


def recommended_browser_channel() -> str:
    if sys.platform == "win32":
        edge_paths = [
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        ]
        if any(path.exists() for path in edge_paths):
            return "msedge"
        chrome_paths = [
            Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        if any(path.exists() for path in chrome_paths):
            return "chrome"
    if sys.platform == "darwin":
        return "chrome"
    return "chromium"


def _load_raw(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("The top level of config.yaml must be a mapping.")
    return data


def _save_raw(config_path: Path, data: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def configure_site(
    *,
    config_path: Path | None,
    data_dir: Path,
    base_url: str,
    login_url: str,
    username: str,
    password: str,
    browser_channel: str,
    proxy: str = "",
) -> dict[str, Any]:
    config_path = (config_path or default_config_path()).expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "browser_profile").mkdir(parents=True, exist_ok=True)
    (data_dir / "materials").mkdir(parents=True, exist_ok=True)
    (data_dir / "assignments").mkdir(parents=True, exist_ok=True)

    raw = _load_raw(config_path)
    raw["app"] = {"data_dir": str(data_dir)}
    raw["browser"] = {
        "channel": browser_channel,
        "executable_path": "",
        "headless": True,
        "profile_dir": "browser_profile",
        "proxy": proxy,
        "timeout_seconds": 30,
    }
    raw["credentials"] = {
        "provider": "file",
        "path": "credentials.ini",
        "section": "moodle",
        "username_env": "HOMEWORK_USERNAME",
        "password_env": "HOMEWORK_PASSWORD",
    }
    raw["site"] = {
        "base_url": base_url.rstrip("/"),
        "login_url": login_url.strip() or f"{base_url.rstrip('/')}/login/index.php",
    }
    raw.setdefault("submission", {})["replace_existing"] = True
    raw.setdefault("courses", {})
    backup = None
    if config_path.exists():
        backup = config_path.with_name(
            f"{config_path.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(config_path, backup)
    _save_raw(config_path, raw)

    credentials_path = data_dir / "credentials.ini"
    credentials = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
    credentials["moodle"] = {"username": username, "password": password}
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    with credentials_path.open("w", encoding="utf-8") as stream:
        credentials.write(stream)
    try:
        credentials_path.chmod(0o600)
    except OSError:
        pass

    return {
        "config": str(config_path),
        "data_dir": str(data_dir),
        "credentials": str(credentials_path),
        "browser_channel": browser_channel,
        "backup": str(backup) if backup else None,
    }


def add_course(
    *,
    config_path: Path | None,
    course_key: str,
    course_name: str,
    course_id: str,
    materials_dir: str | None,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    config_path = (config_path or default_config_path()).expanduser().resolve()
    raw = _load_raw(config_path)
    if not raw:
        raise ConfigError("Configure the Moodle site before adding a course.")

    app = raw.get("app", {})
    data_dir = Path(str(app.get("data_dir", default_data_dir()))).expanduser().resolve()
    materials_value = materials_dir or str(data_dir / "materials" / course_key)
    materials_path = Path(materials_value).expanduser()
    if not materials_path.is_absolute():
        materials_path = data_dir / materials_path
    materials_path = materials_path.resolve()
    materials_path.mkdir(parents=True, exist_ok=True)
    (materials_path / "PUT_IMAGES_HERE.txt").write_text(
        "把课程作业图片放在这个文件夹中。"
        "建议文件名包含章节、页码和题号，例如：第一章_30页_第8题.jpg。\n",
        encoding="utf-8",
    )

    courses = dict(raw.get("courses", {}))
    current = dict(courses.get(course_key, {}))
    current.update(
        {
            "name": course_name,
            "course_id": str(course_id),
            "aliases": list(dict.fromkeys(aliases or [course_key, course_name])),
            "materials_dir": str(materials_path),
        }
    )
    current.setdefault("assignments", {})
    courses[course_key] = current
    raw["courses"] = courses
    _save_raw(config_path, raw)
    return {
        "course_key": course_key,
        "course_name": course_name,
        "course_id": str(course_id),
        "materials_dir": str(materials_path),
        "config": str(config_path),
    }


def set_materials_dir(
    *,
    config_path: Path | None,
    course_key: str,
    materials_dir: str,
    open_after: bool,
) -> dict[str, Any]:
    config_path = (config_path or default_config_path()).expanduser().resolve()
    raw = _load_raw(config_path)
    courses = dict(raw.get("courses", {}))
    if course_key not in courses:
        raise ConfigError(f"Unknown course: {course_key}")

    app = raw.get("app", {})
    data_dir = Path(str(app.get("data_dir", default_data_dir()))).expanduser().resolve()
    path = Path(materials_dir).expanduser()
    if not path.is_absolute():
        path = data_dir / path
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    (path / "PUT_IMAGES_HERE.txt").write_text(
        "把课程作业图片放在这个文件夹中。\n",
        encoding="utf-8",
    )

    course = dict(courses[course_key])
    course["materials_dir"] = str(path)
    courses[course_key] = course
    raw["courses"] = courses
    _save_raw(config_path, raw)
    if open_after:
        open_folder(path)
    return {"course_key": course_key, "materials_dir": str(path), "opened": open_after}


def open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command)


def capability_probe() -> dict[str, Any]:
    probe = Path(str(files("homework_automation.assets").joinpath("capability-probe.png")))
    return {
        "probe_image": str(probe),
        "expected_answer": "PROBE-739; 3 blue circles; 2 red squares",
        "instruction": (
            "Use the host agent's image-reading capability to inspect probe_image. "
            "Only continue if the text and both shape counts are correct."
        ),
    }


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))
