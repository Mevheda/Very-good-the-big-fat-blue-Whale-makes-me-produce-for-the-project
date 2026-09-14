from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from homework_automation.config import load_credentials, load_settings  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_env_credentials_and_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config" / "config.yaml"
            config.parent.mkdir(parents=True)
            config.write_text(
                """
app:
  data_dir: ../data
browser:
  channel: chromium
credentials:
  provider: env
  username_env: TEST_MOODLE_USER
  password_env: TEST_MOODLE_PASSWORD
site:
  base_url: https://moodle.example.edu
courses: {}
""",
                encoding="utf-8",
            )
            old_user = os.environ.get("TEST_MOODLE_USER")
            old_password = os.environ.get("TEST_MOODLE_PASSWORD")
            os.environ["TEST_MOODLE_USER"] = "student"
            os.environ["TEST_MOODLE_PASSWORD"] = "secret"
            try:
                settings = load_settings(config)
                username, password = load_credentials(settings)
            finally:
                if old_user is None:
                    os.environ.pop("TEST_MOODLE_USER", None)
                else:
                    os.environ["TEST_MOODLE_USER"] = old_user
                if old_password is None:
                    os.environ.pop("TEST_MOODLE_PASSWORD", None)
                else:
                    os.environ["TEST_MOODLE_PASSWORD"] = old_password

            self.assertEqual(username, "student")
            self.assertEqual(password, "secret")
            self.assertEqual(settings.data_dir, (root / "data").resolve())
            self.assertEqual(settings.login_url, "https://moodle.example.edu/login/index.php")


if __name__ == "__main__":
    unittest.main()
