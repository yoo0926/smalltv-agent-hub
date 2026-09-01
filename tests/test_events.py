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


class CodexHookTests(unittest.TestCase):
    """Codex sends the same hook payloads Claude does — same event names, same
    field names, delivered on stdin. Its `notify` command only fires when a turn
    ends, so without these the display could never show Codex actually working:
    it stayed on the last "done" it heard about until that aged off."""

    @staticmethod
    def _hook(event, **extra):
        payload = {"hook_event_name": event, "session_id": "abc", "cwd": "/ws/demo"}
        payload.update(extra)
        return normalize_event("codex", payload)

    def test_a_codex_prompt_reports_working(self):
        event = self._hook("UserPromptSubmit")
        self.assertEqual(event["state"], "working")
        self.assertEqual(event["agent"], "codex")

    def test_a_codex_turn_ending_reports_done(self):
        self.assertEqual(self._hook("Stop")["state"], "done")

    def test_codex_waiting_for_approval_asks_for_a_human(self):
        """Codex blocks on PermissionRequest until someone answers, which is
        exactly what the display exists to surface."""
        self.assertEqual(self._hook("PermissionRequest")["state"], "needs_input")

    def test_working_is_not_re_reported_per_tool_call(self):
        """No per-tool-call hook is installed for either agent: the state stays
        working until the turn ends, so paying a subprocess per tool call would
        buy nothing. This pins that PreToolUse carries no state of its own."""
        self.assertIsNone(self._hook("PreToolUse")["state"])

    def test_the_notify_path_still_works(self):
        """The turn-complete notification is a separate integration and predates
        the hooks; installing one must not break the other."""
        event = normalize_event("codex", {"type": "agent-turn-complete", "thread-id": "t1", "cwd": "/ws/demo"})
        self.assertEqual(event["state"], "done")
        self.assertEqual(event["agent"], "codex")
        self.assertEqual(event["message"], "Turn complete")

    def test_an_unknown_codex_notification_still_carries_no_state(self):
        event = normalize_event("codex", {"type": "something-else", "thread-id": "t1"})
        self.assertIsNone(event["state"])


if __name__ == "__main__":
    unittest.main()
