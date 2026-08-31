"""Asynchronous push client for the SmallTV Agent Hub firmware."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


MAX_DEVICE_AGENTS = 4
MAX_DEVICE_LABEL = 20
COMPLETED_VISIBLE_FOR = timedelta(minutes=10)

# Which session speaks for a workspace: the ones asking for a human first, then
# the ones still moving, and only then the ones that have finished.
STATE_PRIORITY = {"done": 1, "working": 2, "failed": 3, "needs_input": 4}

# States that mean the workspace has not wrapped up yet.
LIVE_STATES = frozenset({"working", "needs_input"})

# Branch names shared by every workspace of a repository, so they identify none
# of them.
GENERIC_BRANCHES = frozenset({"main", "master"})


def _workspace_key(agent: Dict[str, Any]) -> str:
    return str(agent.get("workspace_path") or agent.get("workspace") or "")


def _workspace_still_busy(agent: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """Whether any session in the same workspace is still live.

    Only asked about a session that just finished, so the session itself can
    never be the one that answers yes.
    """
    workspace = _workspace_key(agent)
    return any(
        _workspace_key(other) == workspace and str(other.get("state") or "") in LIVE_STATES
        for other in snapshot.get("agents", [])
    )


def _ascii_label(value: Any, fallback: str = "agent") -> str:
    text = "".join(char for char in str(value or "") if " " <= char <= "~")
    text = " ".join(text.split())
    return (text or fallback)[:MAX_DEVICE_LABEL]


def _branch_label(agent: Dict[str, Any]) -> str:
    """The branch, minus the conventional type prefix.

    Conductor names a workspace after its branch with that prefix dropped, so
    ``fix/public-error-user-agent`` becomes ``public-error-user-agent``. Match
    that, because the prefix is noise in twenty columns. A branch that names no
    particular work says less than the workspace does, so it yields.
    """
    branch = str(agent.get("branch") or "").rsplit("/", 1)[-1]
    return "" if branch in GENERIC_BRANCHES else branch


def _display_label(agent: Dict[str, Any]) -> str:
    """Name a workspace by its branch, falling back to the Conductor name.

    ``CONDUCTOR_WORKSPACE_NAME`` is frozen into the agent process environment at
    launch, so a workspace renamed afterwards keeps announcing the codename it
    was created with until a new session replaces it. The branch is re-read from
    git on every event, so it stays current.
    """
    return _ascii_label(_branch_label(agent) or agent.get("workspace"), agent.get("agent") or "agent")


def _is_stale(item: Dict[str, Any], now: datetime) -> bool:
    try:
        updated = datetime.fromisoformat(str(item.get("updated_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return now - updated > COMPLETED_VISIBLE_FOR


def dashboard_payload(snapshot: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    # A Conductor workspace can hold several sessions at once: Claude restarts
    # under a fresh session id, and Codex runs beside it. The display shows the
    # workspace, so the session that most deserves attention speaks for it.
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in snapshot.get("agents", []):
        state = str(item.get("state") or "idle")
        if state == "idle":
            continue
        if state in {"done", "failed"} and _is_stale(item, now):
            continue
        key = _workspace_key(item)
        candidate = {
            "label": _display_label(item),
            "agent": _ascii_label(item.get("agent"), "agent")[:8].lower(),
            "state": state,
        }
        current = groups.get(key)
        if current is None:
            groups[key] = candidate
            order.append(key)
        elif STATE_PRIORITY.get(state, 0) > STATE_PRIORITY.get(current["state"], 0):
            groups[key] = candidate
    return {"agents": [groups[key] for key in order[:MAX_DEVICE_AGENTS]]}


def alert_payload(
    agent: Optional[Dict[str, Any]], snapshot: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    if not agent:
        return None
    state = str(agent.get("state") or "")
    if state == "done":
        # One agent finishing does not mean the workspace is done. Claiming so
        # is what puts a full-screen DONE over work that is still running.
        if snapshot and _workspace_still_busy(agent, snapshot):
            return None
        notify_state = "done"
    elif state in {"needs_input", "failed"}:
        notify_state = "waiting"
    else:
        return None
    label = _display_label(agent)
    if state == "failed":
        label = _ascii_label("FAIL " + label)
    return {"state": notify_state, "ttl": 20, "label": label}


class DeviceNotifier:
    """Coalesce snapshots and push them without delaying coding-agent hooks."""

    def __init__(self, base_url: str, timeout: float = 1.5, refresh_sec: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.refresh_sec = refresh_sec
        self._condition = threading.Condition()
        self._latest: Optional[Dict[str, Any]] = None
        self._alerts: Deque[Dict[str, Any]] = deque(maxlen=16)
        self._dirty = False
        self._stopping = False
        self._last_ok = ""
        self._last_error = ""
        self._thread = threading.Thread(target=self._run, name="smalltv-push", daemon=True)
        self._thread.start()

    def publish(self, snapshot: Dict[str, Any], changed_agent: Optional[Dict[str, Any]] = None) -> None:
        alert = alert_payload(changed_agent, snapshot)
        with self._condition:
            self._latest = dashboard_payload(snapshot)
            self._dirty = True
            if alert:
                self._alerts.append(alert)
            self._condition.notify()

    def status(self) -> Dict[str, Any]:
        with self._condition:
            return {
                "configured": True,
                "url": self.base_url.rstrip("/"),
                "last_ok": self._last_ok,
                "last_error": self._last_error,
            }

    def close(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify()
        self._thread.join(timeout=2)

    def _post(self, path: str, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            if not 200 <= response.status < 300:
                raise OSError(f"HTTP {response.status}")

    def _run(self) -> None:
        while True:
            with self._condition:
                if not self._dirty:
                    self._condition.wait(timeout=self.refresh_sec)
                if self._stopping:
                    return
                latest = self._latest
                alerts = list(self._alerts)
                self._alerts.clear()
                self._dirty = False

            if latest is None:
                continue
            try:
                self._post("api/agents", latest)
                for alert in alerts:
                    self._post("api/notify", alert)
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                with self._condition:
                    self._last_ok = now
                    self._last_error = ""
            except (OSError, HTTPError, URLError) as exc:
                # A later event or the 30-second refresh retries the current
                # dashboard. Old attention overlays are deliberately not
                # replayed after a device has been offline for a long time.
                with self._condition:
                    self._last_error = str(exc)[:160]
