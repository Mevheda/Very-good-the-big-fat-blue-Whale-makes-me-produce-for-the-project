from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

from .config import Settings


def launch_context(playwright, settings: Settings, *, headless: bool | None = None):
    proxy = {"server": settings.proxy_server} if settings.proxy_server else None
    browser_kwargs: dict[str, object] = {}
    channel = settings.browser_channel.strip()
    if channel and channel.casefold() not in {"chromium", "playwright"}:
        browser_kwargs["channel"] = channel
    if settings.browser_executable:
        browser_kwargs["executable_path"] = settings.browser_executable

    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(settings.profile_dir),
        headless=settings.headless if headless is None else headless,
        proxy=proxy,
        **browser_kwargs,
    )


def browser_status(settings: Settings) -> dict[str, object]:
    channel = settings.browser_channel.casefold()
    common_paths: list[Path] = []
    if channel in {"msedge", "edge"}:
        common_paths.extend(
            [
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            ]
        )
    elif channel == "chrome":
        common_paths.extend(
            [
                Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
        )

    executable = settings.browser_executable or next(
        (str(path) for path in common_paths if path and path.exists()),
        shutil.which(channel) or "",
    )

    bundled_chromium = ""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            bundled_chromium = playwright.chromium.executable_path
    except Exception:
        pass

    return {
        "channel": settings.browser_channel,
        "configured_executable": settings.browser_executable or None,
        "detected_executable": executable or None,
        "playwright_chromium": bundled_chromium or None,
        "playwright_browser_present": bool(bundled_chromium and Path(bundled_chromium).exists()),
        "platform": sys.platform,
    }


def find_visible(locator):
    for index in range(locator.count()):
        item = locator.nth(index)
        if item.is_visible():
            return item
    return None


def has_login_form(page: Page) -> bool:
    return (
        page.locator("form#login").count() > 0
        and page.locator("#username").count() > 0
        and page.locator("#password").count() > 0
    )


def has_logout_link(page: Page) -> bool:
    return page.locator('a[href*="logout.php"]').count() > 0


def ensure_logged_in(page: Page, settings: Settings, username: str, password: str) -> None:
    failure_markers = (
        "登录失败",
        "用户名或密码错误",
        "invalid login",
        "incorrect",
        "authentication failed",
    )
    last_url = ""

    for attempt in range(2):
        page.goto(settings.login_url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
        if not has_login_form(page):
            if has_logout_link(page):
                return
            raise RuntimeError(f"Login form not found at {page.url}")

        body = page.locator("body").inner_text(timeout=settings.timeout_ms)
        if any(marker in body for marker in ("验证码", "captcha", "Captcha", "CAPTCHA")):
            raise RuntimeError("The login page requires a CAPTCHA; manual intervention is needed.")

        page.fill("#username", username)
        page.fill("#password", password)
        login_button = page.locator("#loginbtn, button:has-text('登录'), button:has-text('Log in')")
        visible_button = find_visible(login_button)
        if visible_button is None:
            raise RuntimeError("Login button not found.")
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=settings.timeout_ms):
                visible_button.click()
        except Exception:
            pass

        for _ in range(24):
            current = page.locator("body").inner_text(timeout=settings.timeout_ms).casefold()
            if any(marker.casefold() in current for marker in failure_markers):
                raise RuntimeError("The site rejected the username or password.")
            if has_logout_link(page):
                return
            if "/login/" not in page.url and not has_login_form(page):
                return
            last_url = page.url
            page.wait_for_timeout(500)

        if attempt == 0:
            page.wait_for_timeout(800)

    raise RuntimeError(f"Login did not complete. Last URL: {last_url}")


def evidence_dir(base_dir: Path, stage: str) -> Path:
    path = base_dir / "evidence" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{stage}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_evidence(page: Page, directory: Path, prefix: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(directory / f"{prefix}.png"), full_page=True)
    (directory / f"{prefix}.txt").write_text(
        page.locator("body").inner_text(timeout=10_000),
        encoding="utf-8",
    )
