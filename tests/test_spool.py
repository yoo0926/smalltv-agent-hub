import json
import tempfile
import unittest
from pathlib import Path

from geekmagic_hub.hook import minimize_for_spool
from geekmagic_hub.server import replay_spool
from geekmagic_hub.store import StateStore


class SpoolTests(unittest.TestCase):
    def test_spool_payload_drops_prompt_and_response(self):
        payload = {
            "cwd": "/tmp/repo",
            "session_id": "s1",
            "hook_event_name": "Stop",
            "prompt": "private prompt",
            "last_assistant_message": "private response",
            "_desk_hub_conductor": {"is_local": "1"},
        }
        minimized = minimize_for_spool("claude", payload)
        self.assertNotIn("prompt", minimized)
        self.assertNotIn("last_assistant_message", minimized)
        self.assertEqual(minimized["session_id"], "s1")

    def test_replay_spool_consumes_valid_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spool = root / "pending.jsonl"
            envelope = {
                "source": "claude",
                "payload": {
                    "cwd": directory,
                    "session_id": "s2",
                    "hook_event_name": "Stop",
                    "_desk_hub_conductor": {
                        "is_local": "1",
                        "workspace_name": "demo",
                        "workspace_path": directory,
                    },
                },
            }
            spool.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
            store = StateStore(root / "state")
            self.assertEqual(replay_spool(store, spool), 1)
            self.assertFalse(spool.exists())
            self.assertEqual(store.snapshot()["agents"][0]["state"], "done")


if __name__ == "__main__":
    unittest.main()
