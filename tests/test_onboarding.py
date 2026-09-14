from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homework_automation.config import load_credentials, load_settings  # noqa: E402
from homework_automation.onboarding import (  # noqa: E402
    add_course,
    capability_probe,
    configure_site,
)


class OnboardingTests(unittest.TestCase):
    def test_chat_collected_configuration_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config" / "config.yaml"
            data_dir = root / "HomeworkAutomation"
            configure_site(
                config_path=config_path,
                data_dir=data_dir,
                base_url="https://moodle.example.edu",
                login_url="",
                username="student",
                password="secret",
                browser_channel="chromium",
            )
            add_course(
                config_path=config_path,
                course_key="database",
                course_name="Database Systems",
                course_id="11",
                materials_dir=None,
                aliases=["db"],
            )

            settings = load_settings(config_path)
            username, password = load_credentials(settings)
            self.assertEqual(username, "student")
            self.assertEqual(password, "secret")
            self.assertIn("database", settings.raw["courses"])
            materials = Path(settings.raw["courses"]["database"]["materials_dir"])
            self.assertTrue(materials.exists())
            self.assertTrue((materials / "PUT_IMAGES_HERE.txt").exists())

    def test_capability_probe_exists(self) -> None:
        probe = capability_probe()
        self.assertTrue(Path(probe["probe_image"]).exists())


if __name__ == "__main__":
    unittest.main()
