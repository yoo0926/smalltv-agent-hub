import unittest
from datetime import datetime, timedelta

from geekmagic_hub.device import alert_payload, dashboard_payload

# The dashboard hides finished work after a while, so the tests pin "now"
# instead of racing the wall clock.
NOW = datetime.fromisoformat("2026-08-31T01:30:00+00:00")


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
        self.assertEqual(payload["agents"][0]["label"], "a-very-..ce-name")
        self.assertNotIn("message", payload["agents"][0])
        self.assertNotIn("cwd", payload["agents"][0])

    def test_idle_sessions_are_not_sent_to_the_display(self):
        payload = dashboard_payload(
            {"agents": [{"workspace": "old", "agent": "claude", "state": "idle"}]}
        )
        self.assertEqual(payload, {"agents": []})

    def test_one_workspace_is_one_row_even_with_several_sessions(self):
        snapshot = {
            "agents": [
                {
                    "workspace": "datadog-oncall",
                    "workspace_path": "/ws/datadog-oncall",
                    "agent": "codex",
                    "state": "done",
                    "updated_at": "2026-08-31T01:27:19+00:00",
                },
                {
                    "workspace": "datadog-oncall",
                    "workspace_path": "/ws/datadog-oncall",
                    "agent": "claude",
                    "state": "working",
                    "updated_at": "2026-08-31T01:26:50+00:00",
                },
            ]
        }
        payload = dashboard_payload(snapshot, now=NOW)
        self.assertEqual(len(payload["agents"]), 1)
        self.assertEqual(payload["agents"][0]["state"], "working")
        self.assertEqual(payload["agents"][0]["label"], "datadog-oncall")
        self.assertEqual(payload["agents"][0]["agent"], "claude")

    def test_workspace_shows_the_session_that_most_needs_attention(self):
        just_now = NOW.isoformat(timespec="seconds")

        def row(agent, state):
            return {
                "workspace": "shared",
                "workspace_path": "/ws/shared",
                "agent": agent,
                "state": state,
                "updated_at": just_now,
            }

        def state_for(*sessions):
            payload = dashboard_payload({"agents": [row(*s) for s in sessions]}, now=NOW)
            return payload["agents"][0]["state"]

        self.assertEqual(state_for(("claude", "working"), ("codex", "needs_input")), "needs_input")
        self.assertEqual(state_for(("claude", "working"), ("codex", "failed")), "failed")
        self.assertEqual(state_for(("claude", "failed"), ("codex", "needs_input")), "needs_input")

    def test_separate_workspaces_stay_on_separate_rows(self):
        payload = dashboard_payload(
            {
                "agents": [
                    {"workspace": "hub", "workspace_path": "/ws/one", "agent": "claude", "state": "working"},
                    {"workspace": "hub", "workspace_path": "/ws/two", "agent": "claude", "state": "working"},
                ]
            }
        )
        self.assertEqual(len(payload["agents"]), 2)

    def test_branch_outranks_a_workspace_name_left_over_from_creation(self):
        # Conductor freezes CONDUCTOR_WORKSPACE_NAME into the session process at
        # launch, so a workspace renamed afterwards keeps reporting the codename
        # it was created with. The branch is re-read on every event.
        payload = dashboard_payload(
            {
                "agents": [
                    {
                        "workspace": "austin",
                        "workspace_path": "/ws/austin",
                        "branch": "verify-hub-status",
                        "agent": "claude",
                        "state": "working",
                    }
                ]
            }
        )
        self.assertEqual(payload["agents"][0]["label"], "verify-hub-status")

    def test_branch_type_prefix_is_dropped(self):
        payload = dashboard_payload(
            {
                "agents": [
                    {
                        "workspace": "seoul",
                        "workspace_path": "/ws/seoul",
                        "branch": "fix/public-error-user-agent",
                        "agent": "codex",
                        "state": "working",
                    }
                ]
            }
        )
        self.assertEqual(payload["agents"][0]["label"], "public-er..er-agent")

    def test_a_branch_naming_no_particular_work_yields_to_the_workspace(self):
        def label_for(branch):
            payload = dashboard_payload(
                {
                    "agents": [
                        {
                            "workspace": "desk-hub",
                            "workspace_path": "/ws/desk-hub",
                            "branch": branch,
                            "agent": "claude",
                            "state": "working",
                        }
                    ]
                }
            )
            return payload["agents"][0]["label"]

        self.assertEqual(label_for("main"), "desk-hub")
        self.assertEqual(label_for("master"), "desk-hub")
        self.assertEqual(label_for(""), "desk-hub")

    def test_label_falls_back_to_the_agent_when_nothing_names_the_work(self):
        payload = dashboard_payload(
            {"agents": [{"workspace_path": "/ws/none", "agent": "codex", "state": "working"}]}
        )
        self.assertEqual(payload["agents"][0]["label"], "codex")

    def test_alerts_use_the_branch_too(self):
        finished = {
            "workspace": "austin",
            "workspace_path": "/ws/austin",
            "branch": "feature/verify-hub-status",
            "agent": "claude",
            "state": "done",
        }
        self.assertEqual(alert_payload(finished)["label"], "verify-hub-status")
        failed = {**finished, "state": "failed"}
        self.assertEqual(alert_payload(failed)["label"], "FAIL verify-..status")

    def test_branches_alike_at_the_front_stay_apart_on_the_display(self):
        # The two workspaces that produced this feature: their branches share a
        # prefix longer than a two-card row can hold, so cutting the tail would
        # render both as the same name.
        payload = dashboard_payload(
            {
                "agents": [
                    {
                        "workspace_path": "/ws/roseau",
                        "branch": "verify-local-agent-hub-status",
                        "agent": "claude",
                        "state": "working",
                    },
                    {
                        "workspace_path": "/ws/austin",
                        "branch": "verify-local-agent-hub-status-v1",
                        "agent": "claude",
                        "state": "working",
                    },
                ]
            }
        )
        labels = [row["label"] for row in payload["agents"]]
        self.assertEqual(labels, ["verify-..status", "verify-..tus-v1"])
        self.assertEqual(len(set(labels)), 2)

    def test_label_budget_follows_the_layout_the_row_count_picks(self):
        def label_with(rows):
            snapshot = {
                "agents": [
                    {
                        "workspace_path": "/ws/%d" % i,
                        "branch": "flight-monthly-price-improvement",
                        "agent": "claude",
                        "state": "working",
                    }
                    for i in range(rows)
                ]
            }
            return dashboard_payload(snapshot)["agents"][0]["label"]

        # The firmware's own budgets: a lone hero row, a pair of cards, dense rows.
        self.assertEqual(len(label_with(1)), 19)
        self.assertEqual(len(label_with(2)), 15)
        self.assertEqual(len(label_with(3)), 16)
        self.assertEqual(len(label_with(4)), 16)

    def test_a_label_that_already_fits_is_left_alone(self):
        payload = dashboard_payload(
            {
                "agents": [
                    {
                        "workspace_path": "/ws/one",
                        "branch": "eks-migration",
                        "agent": "claude",
                        "state": "working",
                    },
                    {
                        "workspace_path": "/ws/two",
                        "branch": "desk-hub",
                        "agent": "codex",
                        "state": "working",
                    },
                ]
            }
        )
        self.assertEqual([row["label"] for row in payload["agents"]], ["eks-migration", "desk-hub"])

    def test_shortening_keeps_both_ends_and_spends_the_whole_budget(self):
        from geekmagic_hub.device import _shorten

        self.assertEqual(_shorten("datadog-oncall-issue-check", 15), "datadog..-check")
        # An odd budget gives its spare character to the front, which carries
        # more meaning; an even one splits evenly.
        self.assertEqual(_shorten("abcdefghij", 5), "ab..j")
        self.assertEqual(_shorten("abcdefghij", 6), "ab..ij")
        self.assertEqual(_shorten("abcdefghij", 7), "abc..ij")
        for budget in range(3, 20):
            self.assertEqual(len(_shorten("a" * 40, budget)), budget)

    def test_finished_work_leaves_the_display_after_ten_minutes(self):
        def rows_after(minutes):
            finished = (NOW - timedelta(minutes=minutes)).isoformat(timespec="seconds")
            snapshot = {
                "agents": [
                    {
                        "workspace": "wrapped-up",
                        "workspace_path": "/ws/wrapped-up",
                        "agent": "claude",
                        "state": "done",
                        "updated_at": finished,
                    }
                ]
            }
            return dashboard_payload(snapshot, now=NOW)["agents"]

        self.assertEqual(len(rows_after(9)), 1)
        self.assertEqual(rows_after(11), [])

    def test_no_done_alert_while_another_session_is_still_working(self):
        working = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "claude", "state": "working"}
        finished = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "codex", "state": "done"}
        self.assertIsNone(alert_payload(finished, {"agents": [working, finished]}))

    def test_done_alert_fires_once_the_workspace_is_finished(self):
        idle = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "claude", "state": "idle"}
        finished = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "codex", "state": "done"}
        alert = alert_payload(finished, {"agents": [idle, finished]})
        self.assertEqual(alert["state"], "done")

    def test_attention_alerts_are_never_suppressed(self):
        working = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "claude", "state": "working"}
        for state in ("needs_input", "failed"):
            stuck = {"workspace": "shared", "workspace_path": "/ws/shared", "agent": "codex", "state": state}
            self.assertEqual(alert_payload(stuck, {"agents": [working, stuck]})["state"], "waiting")

    def test_alert_mapping(self):
        self.assertEqual(alert_payload({"workspace": "demo", "state": "done"})["state"], "done")
        self.assertEqual(alert_payload({"workspace": "demo", "state": "needs_input"})["state"], "waiting")
        self.assertEqual(alert_payload({"workspace": "demo", "state": "failed"})["label"], "FAIL demo")
        self.assertIsNone(alert_payload({"workspace": "demo", "state": "working"}))


if __name__ == "__main__":
    unittest.main()
