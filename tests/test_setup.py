import tempfile
import unittest
from pathlib import Path

from scripts.setup_macos import (
    SetupConfig,
    build_commands,
    config_from_values,
    load_env_file,
    prompt_config,
    validate_device_url,
    write_env_file,
)


ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def test_shell_wrapper_syntax(self):
        import subprocess

        result = subprocess.run(
            ["/bin/sh", "-n", str(ROOT / "scripts" / "setup_macos.sh")],
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_env_file_round_trip(self):
        config = SetupConfig(
            device_url="http://smalltv-demo.local",
            install_claude=True,
            install_codex=False,
            install_service=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            write_env_file(path, config)
            loaded = config_from_values(load_env_file(path))
        self.assertEqual(loaded, config)

    def test_enter_accepts_env_defaults(self):
        values = {
            "DESK_HUB_DEVICE_URL": "http://smalltv-demo.local",
            "DESK_HUB_INSTALL_CLAUDE": "true",
            "DESK_HUB_INSTALL_CODEX": "false",
            "DESK_HUB_INSTALL_SERVICE": "true",
        }
        answers = iter(["", "", "", ""])
        config = prompt_config(values, lambda _: next(answers))
        self.assertEqual(
            config,
            SetupConfig("http://smalltv-demo.local", True, False, True),
        )

    def test_typed_answers_override_defaults(self):
        values = {
            "DESK_HUB_DEVICE_URL": "http://old.local",
            "DESK_HUB_INSTALL_CLAUDE": "true",
            "DESK_HUB_INSTALL_CODEX": "true",
            "DESK_HUB_INSTALL_SERVICE": "true",
        }
        answers = iter(["n", "y", "y", "http://new.local/"])
        config = prompt_config(values, lambda _: next(answers))
        self.assertEqual(
            config,
            SetupConfig("http://new.local", False, True, True),
        )

    def test_device_url_is_not_prompted_when_service_is_disabled(self):
        values = {
            "DESK_HUB_DEVICE_URL": "http://saved.local",
            "DESK_HUB_INSTALL_CLAUDE": "true",
            "DESK_HUB_INSTALL_CODEX": "true",
            "DESK_HUB_INSTALL_SERVICE": "true",
        }
        answers = iter(["", "", "n"])
        config = prompt_config(values, lambda _: next(answers))
        self.assertEqual(
            config,
            SetupConfig("http://saved.local", True, True, False),
        )

    def test_service_requires_an_http_device_url(self):
        with self.assertRaises(ValueError):
            validate_device_url("smalltv.local")
        self.assertEqual(validate_device_url("", required=False), "")

    def test_commands_respect_agent_choices(self):
        config = SetupConfig("http://smalltv.local", True, False, True)
        commands = build_commands(ROOT, Path("/python"), config, apply=True)
        self.assertEqual(len(commands), 2)
        self.assertIn("--skip-codex", commands[0])
        self.assertNotIn("--skip-claude", commands[0])
        self.assertEqual(commands[0][-1], "--apply")
        self.assertIn("http://smalltv.local", commands[1])
        self.assertEqual(commands[1][-1], "--apply")


if __name__ == "__main__":
    unittest.main()
