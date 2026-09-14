from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

CN_DIGITS = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
    11: "十一",
    12: "十二",
    13: "十三",
    14: "十四",
    15: "十五",
    16: "十六",
    17: "十七",
    18: "十八",
    19: "十九",
    20: "二十",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\-_—–·.，,、：:()（）\[\]【】]+", "", value)


def chapter_aliases(chapter: int) -> list[str]:
    chinese = CN_DIGITS.get(chapter)
    aliases = [f"第{chapter}章", f"{chapter}章", f"ch{chapter}", f"ch{chapter:02d}"]
    if chinese:
        aliases.extend([f"第{chinese}章", f"{chinese}章"])
    return [normalize_text(alias) for alias in aliases]


def parse_assignment_spec(title: str) -> dict[str, object]:
    page_match = re.search(r"(?:第)?(\d+(?:-\d+)?)页", title)
    pages = page_match.group(1) if page_match else ""
    remainder = title[page_match.end() :] if page_match else title
    remainder = remainder.replace("和", "、")
    problems = re.findall(r"(?:\*\d+|\d+(?:（[^）]*）)?)", remainder)
    return {
        "pages": pages,
        "required_problems": list(dict.fromkeys(problems)),
    }


def list_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
    )


def rank_images(root: Path, chapter: int, assignment_title: str) -> list[dict[str, object]]:
    spec = parse_assignment_spec(assignment_title)
    aliases = chapter_aliases(chapter)
    problem_tokens = [
        normalize_text(str(token).replace("*", "").split("（", 1)[0])
        for token in spec["required_problems"]
    ]
    page_numbers = re.findall(r"\d+", str(spec["pages"]))

    ranked: list[dict[str, object]] = []
    for path in list_images(root):
        normalized_name = normalize_text(path.name)
        score = 0
        reasons: list[str] = []
        if any(alias in normalized_name for alias in aliases):
            score += 100
            reasons.append("chapter")
        if any(page in normalized_name for page in page_numbers):
            score += 40
            reasons.append("page")
        matched = [token for token in problem_tokens if token and token in normalized_name]
        if matched:
            score += 10 * len(matched)
            reasons.append("problem")
        ranked.append(
            {
                "path": str(path),
                "name": path.name,
                "score": score,
                "reasons": reasons,
            }
        )

    return sorted(ranked, key=lambda item: (-int(item["score"]), str(item["name"])))


def write_candidates(
    output_path: Path,
    materials_root: Path,
    chapter: int,
    assignment_title: str,
) -> dict[str, object]:
    spec = parse_assignment_spec(assignment_title)
    candidates = rank_images(materials_root, chapter, assignment_title)
    result: dict[str, object] = {
        "materials_root": str(materials_root),
        "chapter": chapter,
        "assignment_title": assignment_title,
        "pages": spec["pages"],
        "required_problems": spec["required_problems"],
        "image_count": len(candidates),
        "candidates": candidates,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
