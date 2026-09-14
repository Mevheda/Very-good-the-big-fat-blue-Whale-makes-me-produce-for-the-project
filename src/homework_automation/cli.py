from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .config import (
    Settings,
    assignment_dir,
    default_config_path,
    get_assignment,
    get_course,
    load_credentials,
    load_settings,
)
from .browser import browser_status
from .docx_builder import build_from_files
from .materials import write_candidates
from .moodle import (
    list_courses,
    read_assignment,
    submit_file,
    sync_course_assignments,
    verify_submission,
)
from .onboarding import (
    add_course,
    capability_probe,
    configure_site,
    default_data_dir,
    open_folder,
    recommended_browser_channel,
    set_materials_dir,
)
from .rendering import render_docx, renderer_status

CN_NUMBERS = [
    "零",
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
]


def chapter_label(chapter: int) -> str:
    return CN_NUMBERS[chapter] if 0 <= chapter < len(CN_NUMBERS) else str(chapter)


def _course_materials_dir(settings: Settings, course: dict[str, Any]) -> Path:
    value = str(course.get("materials_dir", f"materials/{course.get('name', 'course')}"))
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = settings.data_dir / path
    return path.resolve()


def command_init_config(args: argparse.Namespace) -> int:
    target = Path(args.config).expanduser().resolve() if args.config else default_config_path()
    if target.exists() and not args.force:
        raise FileExistsError(f"Configuration already exists: {target}")

    example = Path(__file__).resolve().parents[2] / "config" / "config.example.yaml"
    if not example.exists():
        raise FileNotFoundError(f"Bundled example configuration is missing: {example}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(example, target)
    print(json.dumps({"config": str(target)}, ensure_ascii=False, indent=2))
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    packages = {
        name: importlib.util.find_spec(name) is not None
        for name in ("playwright", "yaml", "docx", "fitz")
    }
    result = {
        "python": sys.version.split()[0],
        "git": shutil.which("git"),
        "packages": packages,
        "renderer": renderer_status(),
        "recommended_browser_channel": recommended_browser_channel(),
        "capability_probe": capability_probe(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(packages.values()) else 1


def command_configure(args: argparse.Namespace) -> int:
    result = configure_site(
        config_path=args.config,
        data_dir=Path(args.data_dir).expanduser() if args.data_dir else default_data_dir(),
        base_url=args.moodle_url,
        login_url=args.login_url or "",
        username=args.username,
        password=args.password,
        browser_channel=args.browser or recommended_browser_channel(),
        proxy=args.proxy or "",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_add_course(args: argparse.Namespace) -> int:
    result = add_course(
        config_path=args.config,
        course_key=args.course_key,
        course_name=args.course_name,
        course_id=str(args.course_id),
        materials_dir=args.materials_dir,
        aliases=args.alias,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_folder(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.path:
        result = set_materials_dir(
            config_path=settings.config_path,
            course_key=args.course,
            materials_dir=args.path,
            open_after=args.open,
        )
    else:
        course = get_course(settings, args.course)
        materials = Path(str(course.get("materials_dir", settings.data_dir / "materials" / args.course)))
        if not materials.is_absolute():
            materials = settings.data_dir / materials
        materials = materials.resolve()
        materials.mkdir(parents=True, exist_ok=True)
        (materials / "PUT_IMAGES_HERE.txt").write_text(
            "把课程作业图片放在这个文件夹中。\n",
            encoding="utf-8",
        )
        if args.open:
            open_folder(materials)
        result = {"course_key": args.course, "materials_dir": str(materials), "opened": args.open}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_list_courses(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    print(json.dumps({"courses": list_courses(settings)}, ensure_ascii=False, indent=2))
    return 0


def command_capability(_: argparse.Namespace) -> int:
    print(json.dumps(capability_probe(), ensure_ascii=False, indent=2))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    browser = browser_status(settings)
    renderer = renderer_status()
    browser["ready"] = bool(
        browser.get("detected_executable") or browser.get("playwright_browser_present")
    )
    renderer["ready"] = bool(renderer.get("libreoffice") or renderer.get("pywin32"))
    checks: dict[str, Any] = {
        "python": sys.version.split()[0],
        "config": str(settings.config_path),
        "data_dir": str(settings.data_dir),
        "config_readable": settings.config_path.exists(),
        "packages": {
            name: importlib.util.find_spec(name) is not None
            for name in ("playwright", "yaml", "docx", "fitz")
        },
        "browser": browser,
        "renderer": renderer,
        "data_dir_writable": os.access(settings.data_dir, os.W_OK) if settings.data_dir.exists() else False,
        "course_count": len(settings.raw.get("courses", {})),
        "capability_probe": capability_probe(),
    }
    try:
        username, password = load_credentials(settings)
        checks["credentials"] = {"ok": bool(username and password)}
    except Exception as exc:
        checks["credentials"] = {"ok": False, "error": str(exc)}
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    ready = (
        all(checks["packages"].values())
        and checks["credentials"]["ok"]
        and checks["course_count"] > 0
        and checks["browser"]["ready"]
        and checks["renderer"]["ready"]
    )
    return 0 if ready else 1


def command_sync_course(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    result = sync_course_assignments(settings, args.course)
    raw = dict(settings.raw)
    courses = dict(raw.get("courses", {}))
    course = dict(courses.get(args.course, {}))
    assignments = dict(course.get("assignments", {}))
    for chapter, item in result["assignments"].items():
        current = dict(assignments.get(str(chapter), {}))
        current.update(item)
        current.setdefault("docx_name", f"第{chapter_label(int(chapter))}章作业.docx")
        assignments[str(chapter)] = current
    course["assignments"] = dict(sorted(assignments.items(), key=lambda pair: int(pair[0])))
    courses[args.course] = course
    raw["courses"] = courses

    backup = settings.config_path.with_name(
        f"{settings.config_path.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    shutil.copy2(settings.config_path, backup)
    settings.config_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(json.dumps({"synced": result, "backup": str(backup)}, ensure_ascii=False, indent=2))
    return 0


def command_prepare(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    course = get_course(settings, args.course)
    assignment = get_assignment(course, args.chapter)
    target_dir = assignment_dir(settings, args.course, args.chapter)
    target_dir.mkdir(parents=True, exist_ok=True)
    website = read_assignment(settings, args.course, args.chapter, target_dir)
    materials_root = _course_materials_dir(settings, course)
    materials = write_candidates(
        target_dir / "candidate-images.json",
        materials_root,
        args.chapter,
        str(assignment["title"]),
    )

    chapter_name = chapter_label(args.chapter)
    assignment_data = {
        "course_key": args.course,
        "course_name": course.get("name", ""),
        "course_id": str(course["course_id"]),
        "chapter": args.chapter,
        "chapter_label": chapter_name,
        "module_id": str(assignment["module_id"]),
        "title": assignment["title"],
        "website_url": assignment.get("url", website["url"]),
        "materials_dir": str(materials_root),
        "candidate_images": [item["path"] for item in materials["candidates"]],
        "pages": materials["pages"],
        "required_problems": materials["required_problems"],
        "docx_name": assignment.get("docx_name", f"第{chapter_name}章作业.docx"),
        "document_title": f"{course.get('name', '')} 第{chapter_name}章作业",
        "subtitle": assignment["title"],
        "section_title": f"第{chapter_name}章",
    }
    (target_dir / "assignment.json").write_text(
        json.dumps(assignment_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    questions_path = target_dir / "questions.json"
    answers_path = target_dir / "answers.json"
    if not questions_path.exists():
        questions_path.write_text(
            json.dumps(
                [
                    {"id": problem, "text": "", "source_images": []}
                    for problem in materials["required_problems"]
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if not answers_path.exists():
        answers_path.write_text(
            json.dumps(
                {problem: [] for problem in materials["required_problems"]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "assignment_dir": str(target_dir),
                "assignment": assignment_data,
                "materials": materials,
                "next": "Use image understanding to fill questions.json and answers.json, then run build.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_build(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    target_dir = assignment_dir(settings, args.course, args.chapter)
    assignment_path = target_dir / "assignment.json"
    if not assignment_path.exists():
        raise FileNotFoundError("Run `prepare` before `build`.")
    assignment = json.loads(assignment_path.read_text(encoding="utf-8"))
    output_path = target_dir / assignment["docx_name"]
    build_from_files(
        assignment_path,
        target_dir / "questions.json",
        target_dir / "answers.json",
        output_path,
    )
    print(json.dumps({"output": str(output_path), "size": output_path.stat().st_size}, ensure_ascii=False, indent=2))
    return 0


def command_render(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    target_dir = assignment_dir(settings, args.course, args.chapter)
    assignment = json.loads((target_dir / "assignment.json").read_text(encoding="utf-8"))
    docx_path = Path(args.file) if args.file else target_dir / assignment["docx_name"]
    result = render_docx(docx_path, Path(args.output_dir) if args.output_dir else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_submit(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    target_dir = assignment_dir(settings, args.course, args.chapter)
    assignment = json.loads((target_dir / "assignment.json").read_text(encoding="utf-8"))
    file_path = Path(args.file) if args.file else target_dir / assignment["docx_name"]
    if not file_path.exists():
        raise FileNotFoundError(f"Submission file does not exist: {file_path}")

    if args.replace_existing is None:
        replace_existing = bool(settings.raw.get("submission", {}).get("replace_existing", False))
    else:
        replace_existing = args.replace_existing
    result = submit_file(
        settings,
        args.course,
        args.chapter,
        target_dir,
        file_path,
        replace_existing=replace_existing,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["submitted"] else 1


def command_verify(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    target_dir = assignment_dir(settings, args.course, args.chapter)
    result = verify_submission(settings, args.course, args.chapter, target_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status_submitted"] and result["file_present"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homework-automation",
        description="Portable Moodle homework automation for Codex and other agents.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml. Defaults to HOMEWORK_AUTOMATION_CONFIG or ./config/config.yaml.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight", help="Check the machine before configuring.")
    preflight.set_defaults(func=command_preflight)

    configure = sub.add_parser("configure", help="Write Moodle and credential settings from agent-collected answers.")
    configure.add_argument("--moodle-url", required=True)
    configure.add_argument("--login-url")
    configure.add_argument("--username", required=True)
    configure.add_argument("--password", required=True)
    configure.add_argument("--data-dir")
    configure.add_argument("--browser")
    configure.add_argument("--proxy")
    configure.set_defaults(func=command_configure)

    add_course_parser = sub.add_parser("add-course", help="Add a selected Moodle course to the config.")
    add_course_parser.add_argument("--course-key", required=True)
    add_course_parser.add_argument("--course-name", required=True)
    add_course_parser.add_argument("--course-id", required=True)
    add_course_parser.add_argument("--materials-dir")
    add_course_parser.add_argument("--alias", action="append", default=[])
    add_course_parser.set_defaults(func=command_add_course)

    list_courses_parser = sub.add_parser("list-courses", help="List courses visible to the configured account.")
    list_courses_parser.set_defaults(func=command_list_courses)

    folder = sub.add_parser("folder", help="Show, create, change, or open the image folder for a course.")
    folder.add_argument("--course", required=True)
    folder.add_argument("--path", help="Set a custom image folder.")
    folder.add_argument("--open", action="store_true")
    folder.set_defaults(func=command_folder)

    capability = sub.add_parser("capability", help="Return the image-capability probe metadata.")
    capability.set_defaults(func=command_capability)

    init_config = sub.add_parser("init-config", help="Internal: copy the example configuration.")
    init_config.add_argument("--force", action="store_true")
    init_config.set_defaults(func=command_init_config)

    doctor = sub.add_parser("doctor", help="Check configuration and Python dependencies.")
    doctor.set_defaults(func=command_doctor)

    sync = sub.add_parser("sync-course", help="Sync assignment metadata from Moodle.")
    sync.add_argument("--course", required=True)
    sync.set_defaults(func=command_sync_course)

    prepare = sub.add_parser("prepare", help="Read an assignment and rank local images.")
    prepare.add_argument("--course", required=True)
    prepare.add_argument("--chapter", type=int, required=True)
    prepare.set_defaults(func=command_prepare)

    build = sub.add_parser("build", help="Build DOCX from questions.json and answers.json.")
    build.add_argument("--course", required=True)
    build.add_argument("--chapter", type=int, required=True)
    build.set_defaults(func=command_build)

    render = sub.add_parser("render", help="Render the generated DOCX to PDF and PNG.")
    render.add_argument("--course", required=True)
    render.add_argument("--chapter", type=int, required=True)
    render.add_argument("--file", type=Path)
    render.add_argument("--output-dir", type=Path)
    render.set_defaults(func=command_render)

    submit = sub.add_parser("submit", help="Upload and submit the generated DOCX.")
    submit.add_argument("--course", required=True)
    submit.add_argument("--chapter", type=int, required=True)
    submit.add_argument("--file", type=Path)
    submit.add_argument("--replace-existing", action="store_true", default=None)
    submit.set_defaults(func=command_submit)

    verify = sub.add_parser("verify", help="Verify the website submission independently.")
    verify.add_argument("--course", required=True)
    verify.add_argument("--chapter", type=int, required=True)
    verify.set_defaults(func=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
