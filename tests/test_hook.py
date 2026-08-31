import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from geekmagic_hub import hook as hook_module
from geekmagic_hub.hook import (
    ACTIVITY_THROTTLE_SEC,
    STAMP_TTL_SEC,
    claim_activity_slot,
    main,
    spool_event,
)


# Nothing listens here, so a hook that decides to send falls back to the spool
# and leaves evidence the test can read.
UNREACHABLE = "http://127.0.0.1:9/api/v1/events"


class ActivityThrottleTests(unittest.TestCase):
    def test_a_second_event_inside_the_window_is_throttled(self):
        with tempfile.TemporaryDirectory() as directory:
            stamp = Path(directory) / "activity-claude-c1.stamp"
            self.assertTrue(claim_activity_slot(stamp, now=1000.0))
            self.assertFalse(claim_activity_slot(stamp, now=1000.0 + ACTIVITY_THROTTLE_SEC - 1))
            self.assertTrue(claim_activity_slot(stamp, now=1000.0 + ACTIVITY_THROTTLE_SEC + 1))

    def test_stamps_from_dead_sessions_are_cleaned_up(self):
        # Conductor churns through session ids, so one stamp per session would
        # otherwise pile up in the cache directory forever.
        with tempfile.TemporaryDirectory() as directory:
            abandoned = Path(directory) / "activity-claude-gone.stamp"
            abandoned.touch()
            os.utime(abandoned, (1000.0, 1000.0))
            live = Path(directory) / "activity-claude-live.stamp"
            claim_activity_slot(live, now=1000.0 + STAMP_TTL_SEC + 1)
            self.assertFalse(abandoned.exists())
            self.assertTrue(live.exists())

    def test_cleanup_leaves_recent_stamps_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            recent = Path(directory) / "activity-claude-other.stamp"
            recent.touch()
            os.utime(recent, (1000.0, 1000.0))
            claim_activity_slot(Path(directory) / "activity-claude-live.stamp", now=1100.0)
            self.assertTrue(recent.exists())

    def test_separate_sessions_do_not_throttle_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "activity-claude-c1.stamp"
            second = Path(directory) / "activity-claude-c2.stamp"
            self.assertTrue(claim_activity_slot(first, now=1000.0))
            self.assertTrue(claim_activity_slot(second, now=1000.0))


class HookThrottleTests(unittest.TestCase):
    def run_hook(self, spool, payload):
        stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            main(["claude", "--allow-non-conductor", "--url", UNREACHABLE, "--spool", str(spool)])
        finally:
            sys.stdin = stdin

    def spooled_events(self, spool):
        if not spool.exists():
            return []
        return [json.loads(line)["payload"]["hook_event_name"] for line in spool.read_text().splitlines()]

    def test_repeated_tool_events_are_sent_once_per_window(self):
        with tempfile.TemporaryDirectory() as directory:
            spool = Path(directory) / "pending.jsonl"
            payload = {"session_id": "c1", "cwd": directory, "hook_event_name": "PostToolUse"}
            for _ in range(5):
                self.run_hook(spool, payload)
            self.assertEqual(self.spooled_events(spool), ["PostToolUse"])

    def test_lifecycle_events_are_never_throttled(self):
        with tempfile.TemporaryDirectory() as directory:
            spool = Path(directory) / "pending.jsonl"
            for event in ("UserPromptSubmit", "Stop", "SessionEnd"):
                self.run_hook(spool, {"session_id": "c1", "cwd": directory, "hook_event_name": event})
            self.assertEqual(
                self.spooled_events(spool), ["UserPromptSubmit", "Stop", "SessionEnd"]
            )


class SpoolSizeTests(unittest.TestCase):
    """The spool is only drained when the server starts, so with the bridge
    stopped it grows for as long as agents keep running. It lives in a cache
    directory, so it has to bound itself."""

    def setUp(self):
        self._original = hook_module.SPOOL_MAX_BYTES
        hook_module.SPOOL_MAX_BYTES = 2000   # keep the test fast; the logic is size-agnostic
        self.addCleanup(setattr, hook_module, "SPOOL_MAX_BYTES", self._original)

    @staticmethod
    def _write(spool, name):
        spool_event(spool, {"source": "claude", "payload": {"session_id": name, "pad": "x" * 60}})

    def test_the_spool_stops_growing_once_it_is_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "pending.jsonl"
            for index in range(500):
                self._write(spool, f"s{index}")
            # Trimming halves the file, so the steady state sits under twice the cap.
            self.assertLessEqual(spool.stat().st_size, hook_module.SPOOL_MAX_BYTES * 2)

    def test_the_newest_events_are_the_ones_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "pending.jsonl"
            for index in range(500):
                self._write(spool, f"s{index}")
            self._write(spool, "newest")
            text = spool.read_text(encoding="utf-8")
            self.assertIn('"newest"', text)
            self.assertNotIn('"s0"', text)

    def test_a_small_spool_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "pending.jsonl"
            for index in range(5):
                self._write(spool, f"s{index}")
            self.assertEqual(len(spool.read_text(encoding="utf-8").splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
