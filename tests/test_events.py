import tempfile
import unittest
from pathlib import Path

from geekmagic_hub.events import normalize_event
from geekmagic_hub.store import StateStore


class EventTests(unittest.TestCase):
    def test_claude_lifecycle(self):
        cwd = "/tmp/conductor-worktree"
        start = normalize_event(
            "claude",
            {
                "session_id": "c1",
                "cwd": cwd,
                "hook_event_name": "UserPromptSubmit",
                "prompt": "fix tests",
                "_desk_hub_conductor": {
                    "is_local": "1",
                    "workspace_name": "auth-fix",
                    "workspace_path": cwd,
                },
            },
        )
        self.assertEqual(start["state"], "working")
        self.assertEqual(start["message"], "Working")
        self.assertEqual(start["session_key"], "claude:c1")
        self.assertEqual(start["workspace"], "auth-fix")
        self.assertTrue(start["conductor_local"])

        done = normalize_event(
            "claude",
            {"session_id": "c1", "cwd": cwd, "hook_event_name": "Stop", "last_assistant_message": "done"},
        )
        self.assertEqual(done["state"], "done")
        self.assertEqual(done["message"], "Turn complete")

    def test_claude_permission_is_needs_input(self):
        event = normalize_event(
            "claude",
            {
                "session_id": "c2",
                "cwd": "/tmp/repo",
                "hook_event_name": "Notification",
                "notification_type": "permission_prompt",
                "message": "Permission required",
            },
        )
        self.assertEqual(event["state"], "needs_input")

    def test_task_completed_does_not_end_main_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.apply(
                "claude",
                {"session_id": "c3", "cwd": directory, "hook_event_name": "UserPromptSubmit", "prompt": "work"},
            )
            store.apply(
                "claude",
                {"session_id": "c3", "cwd": directory, "hook_event_name": "TaskCompleted", "task_subject": "subtask"},
            )
            self.assertEqual(store.snapshot()["agents"][0]["state"], "working")

    def test_tool_activity_returns_a_finished_session_to_working(self):
        # Claude reports Stop at the end of every turn, but a session can pick
        # work back up without a new prompt, so tool activity has to revive it.
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.apply("claude", {"session_id": "c4", "cwd": directory, "hook_event_name": "Stop"})
            self.assertEqual(store.snapshot()["agents"][0]["state"], "done")
            store.apply("claude", {"session_id": "c4", "cwd": directory, "hook_event_name": "PostToolUse"})
            revived = store.snapshot()["agents"][0]
            self.assertEqual(revived["state"], "working")
            self.assertEqual(revived["message"], "Working")

    def test_tool_activity_does_not_revive_a_closed_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.apply("claude", {"session_id": "c5", "cwd": directory, "hook_event_name": "SessionEnd"})
            store.apply("claude", {"session_id": "c5", "cwd": directory, "hook_event_name": "PostToolUse"})
            self.assertEqual(store.snapshot()["agents"][0]["state"], "idle")

    def test_codex_turn_complete(self):
        event = normalize_event(
            "codex",
            {
                "type": "agent-turn-complete",
                "thread-id": "x1",
                "turn-id": "t1",
                "cwd": "/tmp/repo",
                "last-assistant-message": "finished",
            },
        )
        self.assertEqual(event["state"], "done")
        self.assertEqual(event["message"], "Turn complete")
        self.assertEqual(event["session_key"], "codex:x1")


if __name__ == "__main__":
    unittest.main()
