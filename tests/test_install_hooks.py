import json
import unittest

from scripts.install_hooks import (
    add_claude_hooks,
    merge_claude_hooks,
    parse_notify,
    replace_notify,
    rewrite_desk_hub_notify,
)


class InstallHookTests(unittest.TestCase):
    def test_claude_merge_is_idempotent(self):
        settings = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "existing"}]}]}}
        added = add_claude_hooks(settings, "/tmp/desk-hub-event claude")
        self.assertEqual(added, 9)
        self.assertEqual(add_claude_hooks(settings, "/tmp/desk-hub-event claude"), 0)
        commands = [hook["command"] for group in settings["hooks"]["Stop"] for hook in group["hooks"]]
        self.assertEqual(commands, ["existing", "/tmp/desk-hub-event claude"])

    def test_claude_moved_clone_updates_old_hook(self):
        settings = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "/old/clone/bin/desk-hub-event claude",
                            }
                        ]
                    }
                ]
            }
        }
        added, updated = merge_claude_hooks(
            settings, "/new/clone/bin/desk-hub-event claude"
        )
        self.assertEqual((added, updated), (8, 1))
        self.assertEqual(
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "/new/clone/bin/desk-hub-event claude",
        )

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

    def test_nested_codex_chain_updates_moved_clone(self):
        previous = [
            "/old/clone/bin/desk-hub-event",
            "codex",
            "--forward-config",
            "/old/clone/.runtime/codex-forward.json",
        ]
        wrapper = ["other-notifier", "--previous-notify", json.dumps(previous)]
        rewritten, found = rewrite_desk_hub_notify(
            wrapper,
            "/new/clone/bin/desk-hub-event",
            "/new/clone/.runtime/codex-forward.json",
        )
        self.assertTrue(found)
        nested = json.loads(rewritten[2])
        self.assertEqual(nested[0], "/new/clone/bin/desk-hub-event")
        self.assertEqual(nested[3], "/new/clone/.runtime/codex-forward.json")

    def test_nested_codex_chain_preserves_existing_json(self):
        previous = [
            "/current/clone/bin/desk-hub-event",
            "codex",
            "--forward-config",
            "/current/clone/.runtime/codex-forward.json",
        ]
        encoded = json.dumps(previous)
        wrapper = ["other-notifier", "--previous-notify", encoded]
        rewritten, found = rewrite_desk_hub_notify(
            wrapper,
            "/current/clone/bin/desk-hub-event",
            "/current/clone/.runtime/codex-forward.json",
        )
        self.assertTrue(found)
        self.assertEqual(rewritten, wrapper)


if __name__ == "__main__":
    unittest.main()
