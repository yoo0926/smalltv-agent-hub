"""Thread-safe, locally persisted agent state."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List

from .events import normalize_event, utc_now


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
            self._events.append(event)
            self._persist()
            return agent

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
