import unittest

from scripts.install_hooks import add_claude_hooks, parse_notify, replace_notify


class InstallHookTests(unittest.TestCase):
    def test_claude_merge_is_idempotent(self):
        settings = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "existing"}]}]}}
        added = add_claude_hooks(settings, "/tmp/desk-hub-event claude")
        self.assertEqual(added, 9)
        self.assertEqual(add_claude_hooks(settings, "/tmp/desk-hub-event claude"), 0)
        commands = [hook["command"] for group in settings["hooks"]["Stop"] for hook in group["hooks"]]
        self.assertEqual(commands, ["existing", "/tmp/desk-hub-event claude"])

    def test_codex_notify_is_parsed_and_replaced(self):
        original = 'notify = ["old-notifier", "turn-ended"]\nmodel = "example"\n'
        argv, _ = parse_notify(original)
        self.assertEqual(argv, ["old-notifier", "turn-ended"])
        updated = replace_notify(original, ["desk-hub-event", "codex"])
        self.assertIn('notify = ["desk-hub-event", "codex"]', updated)
        self.assertIn('model = "example"', updated)

    def test_codex_notify_is_added_when_missing(self):
        updated = replace_notify('model = "example"\n', ["desk-hub-event", "codex"])
        self.assertTrue(updated.startswith('notify = ["desk-hub-event", "codex"]\n'))


if __name__ == "__main__":
    unittest.main()
