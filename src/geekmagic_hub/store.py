"""Thread-safe, locally persisted agent state."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List

from .events import ACTIVITY_EVENTS, normalize_event, utc_now, workspace_key

# Conductor cycles through session ids quickly, so tracked sessions are capped
# as a backstop even when the per-workspace pruning below cannot apply.
MAX_TRACKED_SESSIONS = 200

# A session in one of these states may still produce work and is never pruned.
LIVE_STATES = frozenset({"working", "needs_input"})


class StateStore:
    def __init__(self, data_dir: Path, max_events: int = 500) -> None:
        self.data_dir = data_dir
        self.state_path = data_dir / "state.json"
        self._lock = threading.RLock()
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max_events)
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        agents = data.get("agents", [])
        if isinstance(agents, list):
            self._agents = {
                item["session_key"]: item
                for item in agents
                if isinstance(item, dict) and item.get("session_key")
            }
        events = data.get("events", [])
        if isinstance(events, list):
            self._events.extend(item for item in events if isinstance(item, dict))

    def _persist(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "generated_at": utc_now(),
            "agents": list(self._agents.values()),
            "events": list(self._events),
        }
        fd, temp_name = tempfile.mkstemp(prefix="state-", suffix=".json", dir=str(self.data_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_name, self.state_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def apply(self, source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = normalize_event(source, payload)
        key = event["session_key"]
        with self._lock:
            previous = self._agents.get(key, {})
            state = event["state"] or previous.get("state") or "idle"
            if event["event"] in ACTIVITY_EVENTS and previous.get("last_event") == "SessionEnd":
                # Hooks are separate processes, so a tool event can land after
                # the session already closed. A closed session stays closed.
                state = previous.get("state") or "idle"
            agent = {
                **previous,
                "source": event["source"],
                "agent": event["agent"],
                "session_id": event["session_id"],
                "session_key": key,
                "workspace": event["workspace"],
                "workspace_path": event["workspace_path"],
                "root_path": event["root_path"],
                "branch": event["branch"],
                "cwd": event["cwd"],
                "conductor_local": event["conductor_local"],
                "state": state,
                "message": event["message"],
                "last_event": event["event"],
                "updated_at": event["received_at"],
            }
            self._agents[key] = agent
            self._prune_replaced_sessions(key, agent)
            self._enforce_session_cap()
            self._events.append(event)
            self._persist()
            return agent

    def _prune_replaced_sessions(self, key: str, agent: Dict[str, Any]) -> None:
        """Drop finished sessions that a newer one in the same workspace replaced.

        Conductor starts a fresh session id whenever a chat restarts, so without
        this the same workspace accumulates rows forever and stale ``done`` ones
        keep speaking for a workspace that has moved on. Sources are kept apart
        so a new Claude session never hides what Codex just did.
        """
        workspace = workspace_key(agent)
        updated_at = str(agent.get("updated_at") or "")
        for other_key, other in list(self._agents.items()):
            if other_key == key or other.get("state") in LIVE_STATES:
                continue
            if other.get("source") != agent.get("source"):
                continue
            if workspace_key(other) != workspace:
                continue
            if str(other.get("updated_at") or "") <= updated_at:
                del self._agents[other_key]

    def _enforce_session_cap(self) -> None:
        excess = len(self._agents) - MAX_TRACKED_SESSIONS
        if excess <= 0:
            return

        def oldest_first(keys):
            return sorted(keys, key=lambda k: str(self._agents[k].get("updated_at") or ""))

        # Finished sessions go first, so a live one is only ever evicted when
        # there is nothing else left to drop. That case is real: a session whose
        # terminal was closed mid-turn never reports an end, so it stays
        # "working" forever and both pruners skip it. Without this fallback the
        # cap could not fire at all and the store grew without bound.
        expendable = oldest_first(k for k, v in self._agents.items() if v.get("state") not in LIVE_STATES)
        if len(expendable) < excess:
            expendable += oldest_first(k for k, v in self._agents.items() if v.get("state") in LIVE_STATES)
        for key in expendable[:excess]:
            del self._agents[key]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            agents = sorted(self._agents.values(), key=lambda item: item.get("updated_at", ""), reverse=True)
            counts: Dict[str, int] = {}
            for agent in agents:
                state = str(agent.get("state", "idle"))
                counts[state] = counts.get(state, 0) + 1
            return {"generated_at": utc_now(), "counts": counts, "agents": agents}

    def events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)[-max(1, min(limit, 500)) :]
