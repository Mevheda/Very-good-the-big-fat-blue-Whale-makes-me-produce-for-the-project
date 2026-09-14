#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homework_automation.rendering import render_docx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX pages to PDF and PNG.")
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    result = render_docx(args.docx, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
