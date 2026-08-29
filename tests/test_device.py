import unittest

from geekmagic_hub.device import alert_payload, dashboard_payload


class DevicePayloadTests(unittest.TestCase):
    def test_dashboard_is_small_and_privacy_minimized(self):
        snapshot = {
            "agents": [
                {
                    "workspace": "a-very-long-workspace-name",
                    "agent": "claude",
                    "state": "working",
                    "message": "private details",
                    "cwd": "/private/path",
                },
                {"workspace": "two", "agent": "codex", "state": "done"},
                {"workspace": "three", "agent": "claude", "state": "working"},
                {"workspace": "four", "agent": "claude", "state": "failed"},
                {"workspace": "five", "agent": "claude", "state": "working"},
            ]
        }
        payload = dashboard_payload(snapshot)
        self.assertEqual(len(payload["agents"]), 4)
        self.assertEqual(payload["agents"][0]["label"], "a-very-long-workspac")
        self.assertNotIn("message", payload["agents"][0])
        self.assertNotIn("cwd", payload["agents"][0])

    def test_idle_sessions_are_not_sent_to_the_display(self):
        payload = dashboard_payload(
            {"agents": [{"workspace": "old", "agent": "claude", "state": "idle"}]}
        )
        self.assertEqual(payload, {"agents": []})

    def test_alert_mapping(self):
        self.assertEqual(alert_payload({"workspace": "demo", "state": "done"})["state"], "done")
        self.assertEqual(alert_payload({"workspace": "demo", "state": "needs_input"})["state"], "waiting")
        self.assertEqual(alert_payload({"workspace": "demo", "state": "failed"})["label"], "FAIL demo")
        self.assertIsNone(alert_payload({"workspace": "demo", "state": "working"}))


if __name__ == "__main__":
    unittest.main()
