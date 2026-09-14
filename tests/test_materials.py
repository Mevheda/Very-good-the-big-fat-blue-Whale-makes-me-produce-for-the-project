from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homework_automation.materials import (  # noqa: E402
    chapter_aliases,
    parse_assignment_spec,
    rank_images,
)


class MaterialsTests(unittest.TestCase):
    def test_parse_assignment_spec(self) -> None:
        result = parse_assignment_spec("第二章作业：64页，第3、*6题（只用关系代数）")
        self.assertEqual(result["pages"], "64")
        self.assertEqual(result["required_problems"], ["3", "*6"])

    def test_parse_assignment_spec_with_subquestions(self) -> None:
        result = parse_assignment_spec("第12章作业：352页 10（1、2、3小题）、11题")
        self.assertEqual(result["pages"], "352")
        self.assertEqual(result["required_problems"], ["10（1、2、3小题）", "11"])

    def test_chapter_aliases(self) -> None:
        aliases = chapter_aliases(2)
        self.assertIn("第2章", aliases)
        self.assertIn("第二章", aliases)
        self.assertIn("ch02", aliases)

    def test_rank_images_prefers_filename_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第一章_30页.jpg").write_bytes(b"image")
            (root / "第五章_166页.jpg").write_bytes(b"image")
            ranked = rank_images(root, 1, "第一章作业：30页，第8和14题")
            self.assertEqual(ranked[0]["name"], "第一章_30页.jpg")
            self.assertGreater(int(ranked[0]["score"]), 0)


if __name__ == "__main__":
    unittest.main()
