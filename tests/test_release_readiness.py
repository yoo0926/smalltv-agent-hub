import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "smalltv-agent-hub"


class ReleaseReadinessTests(unittest.TestCase):
    def test_firmware_identity_points_to_this_repository(self):
        config = (FIRMWARE / "src" / "config.h").read_text(encoding="utf-8")
        self.assertIn('#define SELF_UPDATE_ENABLED 0', config)
        self.assertIn(
            '#define REPO_URL      "https://github.com/yoo0926/smalltv-agent-hub"',
            config,
        )
        self.assertIn(
            '#define UPDATE_ASSET "smalltv-agent-hub-esp32-pro-ota.bin"',
            config,
        )
        self.assertNotIn('REPO_NAME     "smalltv-mod"', config)

    def test_ci_and_firmware_document_the_same_artifact_names(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        readme = (FIRMWARE / "README.md").read_text(encoding="utf-8")
        for name in (
            "smalltv-agent-hub-esp32-pro-ota.bin",
            "smalltv-agent-hub-esp32-pro-factory.bin",
        ):
            self.assertIn(name, workflow)
            self.assertIn(name, readme)

    def test_manual_update_ui_has_no_dead_self_update_controls(self):
        webui = (FIRMWARE / "src" / "webui.html").read_text(encoding="utf-8")
        self.assertIn("Automatic release downloads are disabled", webui)
        self.assertNotIn("function checkUpdate()", webui)
        self.assertNotIn("function selfUpdate()", webui)

    def test_inherited_site_and_nested_workflows_are_removed(self):
        self.assertFalse((FIRMWARE / "docs").exists())
        self.assertFalse((FIRMWARE / ".github" / "workflows").exists())

    def test_upstream_attribution_is_preserved(self):
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        readme = (FIRMWARE / "README.md").read_text(encoding="utf-8")
        self.assertIn("giovi321/smalltv-mod", notices)
        self.assertIn("giovi321/smalltv-mod", readme)


if __name__ == "__main__":
    unittest.main()
