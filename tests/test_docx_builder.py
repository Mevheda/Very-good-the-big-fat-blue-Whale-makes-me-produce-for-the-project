from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docx import Document  # noqa: E402

from homework_automation.docx_builder import build_docx  # noqa: E402


class DocxBuilderTests(unittest.TestCase):
    def test_build_docx_contains_question_and_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "chapter.docx"
            build_docx(
                {
                    "title": "Chapter 1",
                    "document_title": "Course Chapter 1",
                    "subtitle": "Questions 1 and 2",
                    "section_title": "Chapter 1",
                },
                [{"id": "1", "text": "What is a database?"}],
                {"1": [{"style": "paragraph", "text": "A structured data collection."}]},
                output,
            )
            text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
            self.assertIn("Course Chapter 1", text)
            self.assertIn("What is a database?", text)
            self.assertIn("A structured data collection.", text)


if __name__ == "__main__":
    unittest.main()
