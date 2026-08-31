import tempfile
import unittest
from pathlib import Path

from geekmagic_hub.store import MAX_TRACKED_SESSIONS, StateStore


def claude_event(session_id, hook_event, workspace="alpha"):
    path = f"/ws/{workspace}"
    return {
        "session_id": session_id,
        "cwd": path,
        "hook_event_name": hook_event,
        "_desk_hub_conductor": {
            "is_local": "1",
            "workspace_name": workspace,
            "workspace_path": path,
            "root_path": path,
        },
    }


def codex_event(thread_id, workspace="alpha"):
    path = f"/ws/{workspace}"
    return {
        "thread-id": thread_id,
        "cwd": path,
        "type": "agent-turn-complete",
        "_desk_hub_conductor": {
            "is_local": "1",
            "workspace_name": workspace,
            "workspace_path": path,
            "root_path": path,
        },
    }


class StorePruningTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.store = StateStore(Path(self._directory.name))

    def keys(self):
        return sorted(agent["session_key"] for agent in self.store.snapshot()["agents"])

    def test_a_finished_session_is_dropped_once_the_workspace_moves_on(self):
        self.store.apply("claude", claude_event("s1", "UserPromptSubmit"))
        self.store.apply("claude", claude_event("s1", "SessionEnd"))
        self.store.apply("claude", claude_event("s2", "UserPromptSubmit"))
        self.assertEqual(self.keys(), ["claude:s2"])

    def test_sessions_still_running_are_never_dropped(self):
        self.store.apply("claude", claude_event("s1", "UserPromptSubmit"))
        self.store.apply("claude", claude_event("s2", "UserPromptSubmit"))
        self.assertEqual(self.keys(), ["claude:s1", "claude:s2"])

    def test_a_waiting_session_is_never_dropped(self):
        self.store.apply(
            "claude",
            {**claude_event("s1", "Notification"), "notification_type": "permission_prompt"},
        )
        self.store.apply("claude", claude_event("s2", "UserPromptSubmit"))
        self.assertEqual(self.keys(), ["claude:s1", "claude:s2"])

    def test_codex_is_not_evicted_by_a_new_claude_session(self):
        self.store.apply("codex", codex_event("x1"))
        self.store.apply("claude", claude_event("s2", "UserPromptSubmit"))
        self.assertEqual(self.keys(), ["claude:s2", "codex:x1"])

    def test_other_workspaces_are_untouched(self):
        self.store.apply("claude", claude_event("s1", "SessionEnd", workspace="beta"))
        self.store.apply("claude", claude_event("s2", "UserPromptSubmit", workspace="alpha"))
        self.assertEqual(self.keys(), ["claude:s1", "claude:s2"])

    def test_the_store_does_not_grow_without_bound(self):
        for index in range(MAX_TRACKED_SESSIONS + 25):
            self.store.apply("claude", claude_event(f"s{index}", "SessionEnd", workspace=f"ws{index}"))
        self.assertLessEqual(len(self.store.snapshot()["agents"]), MAX_TRACKED_SESSIONS)


if __name__ == "__main__":
    unittest.main()
