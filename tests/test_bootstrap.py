import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_macos.sh"


class BootstrapTests(unittest.TestCase):
    def test_shell_syntax(self):
        result = subprocess.run(["/bin/sh", "-n", str(SCRIPT)], check=False)
        self.assertEqual(result.returncode, 0)

    def test_help_is_safe_without_installing(self):
        result = subprocess.run(
            ["/bin/sh", str(SCRIPT), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--install-hooks", result.stdout)
        self.assertIn("--install-service", result.stdout)
        self.assertIn("--build", result.stdout)

    def test_platformio_is_exactly_pinned(self):
        requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("platformio==6.1.19", requirements)

    def test_recommended_python_is_exactly_recorded(self):
        version = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "3.14.7")

    def test_esp32_platform_is_not_floating(self):
        config = (
            ROOT / "firmware" / "smalltv-agent-hub" / "platformio.ini"
        ).read_text(encoding="utf-8")
        self.assertIn("releases/download/55.03.311/", config)
        self.assertNotIn("releases/download/stable/", config)

    def test_generated_ui_check_allows_a_consistent_working_tree(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('WEBUI_HEADER_BEFORE=$(cksum "$WEBUI_HEADER")', script)
        self.assertIn('WEBUI_HEADER_AFTER=$(cksum "$WEBUI_HEADER")', script)
        self.assertNotIn("git -C \"$PROJECT_DIR\" diff --quiet", script)


if __name__ == "__main__":
    unittest.main()
