from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from .browser import (
    ensure_logged_in,
    evidence_dir,
    find_visible,
    launch_context,
    save_evidence,
)
from .config import Settings, get_assignment, get_course, load_credentials

CN_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}


def parse_chapter_number(title: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*章", title)
    if match:
        return int(match.group(1))
    match = re.search(
        r"第\s*(十一|十二|十|一|二|三|四|五|六|七|八|九)\s*章",
        title,
    )
    return CN_NUMBERS.get(match.group(1)) if match else None


def _navigate_from_sidebar(page, settings: Settings, course: dict, assignment: dict) -> None:
    course_id = str(course["course_id"])
    module_id = str(assignment["module_id"])
    assignment_title = str(assignment["title"])
    page.goto(
        f"{settings.base_url}/course/view.php?id={course_id}",
        wait_until="domcontentloaded",
        timeout=settings.timeout_ms,
    )
    page.wait_for_timeout(900)

    candidates = page.locator(f'a[href*="/mod/assign/view.php?id={module_id}"]')
    target = None
    for index in range(candidates.count()):
        item = candidates.nth(index)
        text = re.sub(r"\s+", " ", item.inner_text()).strip()
        if item.is_visible() and text == assignment_title:
            target = item
            break
    if target is None:
        raise RuntimeError(f"Assignment link was not found in the course sidebar: {assignment_title}")

    target.click()
    page.wait_for_load_state("domcontentloaded", timeout=settings.timeout_ms)
    if f"id={module_id}" not in page.url:
        raise RuntimeError(f"Sidebar navigation opened the wrong assignment: {page.url}")


def read_assignment(
    settings: Settings,
    course_key: str,
    chapter: int,
    assignment_dir: Path,
) -> dict[str, Any]:
    course = get_course(settings, course_key)
    assignment = get_assignment(course, chapter)
    username, password = load_credentials(settings)
    evidence = evidence_dir(assignment_dir, "read-assignment")

    with sync_playwright() as playwright:
        context = launch_context(playwright, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(settings.timeout_ms)
        try:
            ensure_logged_in(page, settings, username, password)
            _navigate_from_sidebar(page, settings, course, assignment)
            body = page.locator("body").inner_text(timeout=settings.timeout_ms)
            save_evidence(page, evidence, "assignment-page")
            result = {
                "course_key": course_key,
                "course_name": course.get("name", ""),
                "course_id": str(course["course_id"]),
                "chapter": chapter,
                "module_id": str(assignment["module_id"]),
                "title": assignment["title"],
                "url": page.url,
                "page_title": page.title(),
                "body_text": body,
            }
        finally:
            context.close()

    (assignment_dir / "website-assignment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def sync_course_assignments(settings: Settings, course_key: str) -> dict[str, Any]:
    course = get_course(settings, course_key)
    username, password = load_credentials(settings)
    course_id = str(course["course_id"])

    with sync_playwright() as playwright:
        context = launch_context(playwright, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(settings.timeout_ms)
        try:
            ensure_logged_in(page, settings, username, password)
            page.goto(
                f"{settings.base_url}/mod/assign/index.php?id={course_id}",
                wait_until="domcontentloaded",
                timeout=settings.timeout_ms,
            )
            page.wait_for_timeout(1000)
            rows = page.eval_on_selector_all(
                'a[href*="/mod/assign/view.php?id="]',
                r"""
                links => links.map((a) => {
                  const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
                  const url = new URL(a.href);
                  return {
                    title: text,
                    module_id: url.searchParams.get('id'),
                    url: url.origin + url.pathname + '?id=' + url.searchParams.get('id'),
                    visible: !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length)
                  };
                }).filter((item) => item.visible && item.title && item.module_id)
                """,
            )
        finally:
            context.close()

    deduped = {str(item["module_id"]): item for item in rows}
    assignments: dict[str, dict[str, str]] = {}
    for item in deduped.values():
        chapter = parse_chapter_number(str(item["title"]))
        if chapter is None:
            continue
        assignments[str(chapter)] = {
            "module_id": str(item["module_id"]),
            "title": str(item["title"]),
            "url": str(item["url"]),
        }

    return {
        "course_key": course_key,
        "course_name": course.get("name", ""),
        "course_id": course_id,
        "assignments": dict(sorted(assignments.items(), key=lambda pair: int(pair[0]))),
        "synced_at": datetime.now().isoformat(timespec="seconds"),
    }


def list_courses(settings: Settings) -> list[dict[str, str]]:
    username, password = load_credentials(settings)
    with sync_playwright() as playwright:
        context = launch_context(playwright, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(settings.timeout_ms)
        try:
            ensure_logged_in(page, settings, username, password)
            page.goto(
                f"{settings.base_url}/my/courses.php",
                wait_until="domcontentloaded",
                timeout=settings.timeout_ms,
            )
            page.wait_for_timeout(1200)
            rows = page.eval_on_selector_all(
                'a[href*="/course/view.php?id="]',
                r"""
                links => links.map((a) => {
                  const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
                  const url = new URL(a.href);
                  return {
                    name: text,
                    course_id: url.searchParams.get('id'),
                    url: url.origin + url.pathname + '?id=' + url.searchParams.get('id'),
                    visible: !!(a.offsetWidth || a.offsetHeight || a.getClientRects().length)
                  };
                }).filter((item) => item.visible && item.name && item.course_id)
                """,
            )
        finally:
            context.close()

    deduped: dict[str, dict[str, str]] = {}
    for item in rows:
        deduped[str(item["course_id"])] = {
            "name": str(item["name"]),
            "course_id": str(item["course_id"]),
            "url": str(item["url"]),
        }
    return sorted(deduped.values(), key=lambda item: int(item["course_id"]))


def _click_confirm_if_present(page) -> bool:
    confirm = page.locator(
        '.modal.show button:has-text("继续"), '
        '.modal.show input[value*="继续"], '
        '.modal.show button:has-text("确定"), '
        '.modal.show input[value*="确定"], '
        'button:has-text("Continue"), button:has-text("Confirm"), '
        'button:has-text("继续"), button:has-text("确定")'
    )
    visible = find_visible(confirm)
    if visible is None:
        return False
    visible.click()
    return True


def _upload_file(page, file_path: Path) -> None:
    file_inputs = page.locator('input[type="file"]')
    if file_inputs.count() > 0:
        file_inputs.first.set_input_files(str(file_path))
    else:
        add_file = page.locator('.fp-btn-add a[title*="添加"], .fp-btn-add a[title*="Add"]')
        add_visible = find_visible(add_file)
        if add_visible is None:
            raise RuntimeError("Moodle file picker add button was not found.")
        add_visible.click()
        page.wait_for_timeout(500)

        upload_tab = page.get_by_role("link", name=re.compile("上传一个文件|Upload a file"))
        tab_visible = find_visible(upload_tab)
        if tab_visible is None:
            raise RuntimeError("Moodle upload tab was not found.")
        tab_visible.click()
        page.wait_for_timeout(700)

        repo_input = page.locator('input[type="file"][name="repo_upload_file"]')
        repo_visible = find_visible(repo_input)
        if repo_visible is None:
            raise RuntimeError("Moodle upload input was not found.")
        repo_visible.set_input_files(str(file_path))

        upload_button = page.locator(
            'button.fp-upload-btn, '
            'button:has-text("上传此文件"), '
            'button:has-text("Upload this file")'
        )
        upload_visible = find_visible(upload_button)
        if upload_visible is None:
            raise RuntimeError("Moodle upload confirmation button was not found.")
        upload_visible.click()
        page.wait_for_timeout(1800)

    page.wait_for_timeout(800)
    managers = page.locator(".filemanager")
    manager = next(
        (managers.nth(index) for index in range(managers.count()) if managers.nth(index).is_visible()),
        None,
    )
    if manager is None:
        raise RuntimeError("The visible file manager was not found.")
    if file_path.name not in manager.inner_text(timeout=10_000):
        raise RuntimeError(f"The uploaded file is not visible in the form: {file_path.name}")


def submit_file(
    settings: Settings,
    course_key: str,
    chapter: int,
    assignment_dir: Path,
    file_path: Path,
    *,
    replace_existing: bool,
) -> dict[str, Any]:
    course = get_course(settings, course_key)
    assignment = get_assignment(course, chapter)
    username, password = load_credentials(settings)
    evidence = evidence_dir(assignment_dir, "submit")
    result: dict[str, Any] = {
        "course_key": course_key,
        "chapter": chapter,
        "module_id": str(assignment["module_id"]),
        "title": assignment["title"],
        "submission_file": file_path.name,
        "submitted": False,
        "reason": None,
        "final_url": None,
        "evidence_dir": str(evidence),
    }

    with sync_playwright() as playwright:
        context = launch_context(playwright, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(settings.timeout_ms)
        try:
            ensure_logged_in(page, settings, username, password)
            _navigate_from_sidebar(page, settings, course, assignment)

            add_link = page.locator(
                'a[href*="action=editsubmission"], '
                'button:has-text("添加作业"), a:has-text("添加作业"), '
                'button:has-text("添加提交"), a:has-text("添加提交"), '
                'button:has-text("Add submission"), a:has-text("Add submission")'
            )
            add_visible = find_visible(add_link)
            if add_visible is None and replace_existing:
                remove_button = page.locator(
                    'button:has-text("移除作业"), input[value*="移除作业"], '
                    'a:has-text("移除作业"), button:has-text("Remove submission"), '
                    'a:has-text("Remove submission")'
                )
                remove_visible = find_visible(remove_button)
                if remove_visible is None:
                    raise RuntimeError("Existing submission could not be removed.")
                save_evidence(page, evidence, "before-remove")
                remove_visible.click()
                page.wait_for_timeout(700)
                if _click_confirm_if_present(page):
                    save_evidence(page, evidence, "remove-confirmation")
                    page.wait_for_load_state("domcontentloaded", timeout=settings.timeout_ms)
                    page.wait_for_timeout(900)
                add_visible = find_visible(add_link)

            if add_visible is None:
                body = page.locator("body").inner_text(timeout=10_000)
                if "已提交" in body or "Submitted" in body:
                    raise RuntimeError("The assignment is already submitted and replacement is disabled.")
                raise RuntimeError("The add-submission entry was not found.")

            add_visible.click()
            page.wait_for_load_state("domcontentloaded", timeout=settings.timeout_ms)
            page.wait_for_timeout(700)
            save_evidence(page, evidence, "submission-form")
            _upload_file(page, file_path)
            save_evidence(page, evidence, "after-file-select")

            save_button = page.locator(
                '#id_submitbutton, button:has-text("保存更改"), '
                'input[value*="保存更改"], button:has-text("Save changes")'
            )
            save_visible = find_visible(save_button)
            if save_visible is None:
                raise RuntimeError("Save button was not found.")
            save_visible.click()
            page.wait_for_load_state("domcontentloaded", timeout=settings.timeout_ms)
            page.wait_for_timeout(1200)
            save_evidence(page, evidence, "after-save")

            body = page.locator("body").inner_text(timeout=10_000)
            if "已提交" in body or "Submitted for grading" in body:
                result.update(
                    {
                        "submitted": True,
                        "reason": "The Moodle site submitted automatically after save.",
                        "final_url": page.url,
                    }
                )
            else:
                checkboxes = page.locator('input[type="checkbox"]:visible')
                if checkboxes.count() > 0:
                    raise RuntimeError("A visible confirmation checkbox requires manual handling.")
                submit_button = page.locator(
                    'button:has-text("提交作业"), input[value*="提交作业"], '
                    'a:has-text("提交作业"), button:has-text("Submit assignment")'
                )
                submit_visible = find_visible(submit_button)
                if submit_visible is None:
                    raise RuntimeError("Final submit button was not found.")
                submit_visible.click()
                page.wait_for_timeout(700)
                if not _click_confirm_if_present(page):
                    raise RuntimeError("Final submit confirmation was not found.")
                page.wait_for_load_state("domcontentloaded", timeout=settings.timeout_ms)
                page.wait_for_timeout(1000)
                save_evidence(page, evidence, "after-submit")
                body = page.locator("body").inner_text(timeout=10_000)
                if "已提交" not in body and "Submitted" not in body:
                    raise RuntimeError("Submission status was not confirmed after the final click.")
                result.update(
                    {
                        "submitted": True,
                        "reason": "Submission completed.",
                        "final_url": page.url,
                    }
                )
        except Exception as exc:
            result["reason"] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
            try:
                save_evidence(page, evidence, "error")
            except Exception:
                pass
        finally:
            context.close()

    (evidence / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def verify_submission(
    settings: Settings,
    course_key: str,
    chapter: int,
    assignment_dir: Path,
) -> dict[str, Any]:
    course = get_course(settings, course_key)
    assignment = get_assignment(course, chapter)
    username, password = load_credentials(settings)
    evidence = evidence_dir(assignment_dir, "verify")

    with sync_playwright() as playwright:
        context = launch_context(playwright, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(settings.timeout_ms)
        try:
            ensure_logged_in(page, settings, username, password)
            _navigate_from_sidebar(page, settings, course, assignment)
            body = page.locator("body").inner_text(timeout=settings.timeout_ms)
            docx_name = str(assignment.get("docx_name", ""))
            result = {
                "course_key": course_key,
                "chapter": chapter,
                "module_id": str(assignment["module_id"]),
                "title": assignment["title"],
                "docx_name": docx_name,
                "status_submitted": "已提交" in body or "Submitted" in body,
                "file_present": bool(docx_name and docx_name in body),
                "final_url": page.url,
                "verified_at": datetime.now().isoformat(timespec="seconds"),
            }
            save_evidence(page, evidence, "verified-submission")
            (evidence / "verification.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            context.close()
    return result
