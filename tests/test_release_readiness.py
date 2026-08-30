import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "smalltv-agent-hub"


class ReleaseReadinessTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        ignored_parts = {
            ".git",
            ".pio",
            ".pio-core",
            ".venv",
            "references",
            "tmp",
        }
        documents = [
            path
            for path in ROOT.rglob("*.md")
            if not ignored_parts.intersection(path.relative_to(ROOT).parts)
        ]
        pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for raw_target in pattern.findall(text):
                target = raw_target.strip().split()[0].strip("<>")
                if not target or target.startswith(
                    ("#", "http://", "https://", "mailto:")
                ):
                    continue
                relative = unquote(target.split("#", 1)[0])
                self.assertTrue(
                    (document.parent / relative).exists(),
                    f"broken link in {document.relative_to(ROOT)}: {target}",
                )

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

    def test_root_license_and_security_policy_are_public_ready(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 yoo0926", license_text)
        self.assertIn("/security/advisories/new", security)
        self.assertNotIn("REPLACE WITH", security)
        self.assertFalse((ROOT / "SECURITY.md.template").exists())

    def test_korean_onboarding_guides_are_linked(self):
        pairs = (("README.md", "README.ko.md"), ("MIGRATION.md", "MIGRATION.ko.md"))
        for english_name, korean_name in pairs:
            english = (ROOT / english_name).read_text(encoding="utf-8")
            korean = (ROOT / korean_name).read_text(encoding="utf-8")
            self.assertIn(f"[한국어]({korean_name})", english)
            self.assertIn(f"[English]({english_name})", korean)
            self.assertIn("./scripts/bootstrap_macos.sh --build", korean)
            self.assertIn("./scripts/setup_macos.sh", korean)

    def test_all_onboarding_docs_use_the_current_two_step_flow(self):
        names = (
            "README.md",
            "README.ko.md",
            "MIGRATION.md",
            "MIGRATION.ko.md",
            "CONTRIBUTING.md",
            "PUBLIC_RELEASE_CHECKLIST.md",
        )
        for name in names:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("--install-hooks", text, name)
            self.assertNotIn("--install-service", text, name)
            self.assertNotIn("bootstrap_macos.sh --device-url", text, name)
        for name in (
            "README.md",
            "README.ko.md",
            "MIGRATION.md",
            "MIGRATION.ko.md",
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("./scripts/bootstrap_macos.sh --build", text, name)
            self.assertIn("./scripts/setup_macos.sh", text, name)

    def test_publication_docs_are_timeless(self):
        checklist = (ROOT / "PUBLIC_RELEASE_CHECKLIST.md").read_text(
            encoding="utf-8"
        )
        settings = (ROOT / "REPOSITORY_SETTINGS.md").read_text(encoding="utf-8")
        self.assertNotIn("CI run #", checklist)
        self.assertNotIn("Reviewed against", settings)


if __name__ == "__main__":
    unittest.main()
