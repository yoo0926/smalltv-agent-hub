"""Asynchronous push client for the SmallTV Agent Hub firmware."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .events import workspace_key


MAX_DEVICE_AGENTS = 4
# The alert screen centres one line of size-2 text across 240 px, which is the
# firmware's NOTIFY_LABEL_MAX.
MAX_DEVICE_LABEL = 20
# How many characters the Agent Hub layout leaves for a label, keyed by the
# number of rows on screen. These mirror the compactLabel() budgets in the
# firmware's AgentMode.cpp: a lone hero row is roomier than a pair of cards.
# Spending the same budget here keeps the firmware from cutting a second time,
# from the front, which would undo the shortening below.
LAYOUT_LABEL_BUDGET = {1: 19, 2: 15, 3: 16, 4: 16}
COMPLETED_VISIBLE_FOR = timedelta(minutes=10)

# A session only leaves "working" when it reports an end, so a terminal closed
# mid-turn leaves one running forever. The store keeps those on purpose, but the
# display has four rows: past this window a live session is treated as abandoned
# so it stops speaking for its workspace. Long enough that no real turn reaches
# it, short enough that a forgotten row does not survive the day.
LIVE_VISIBLE_FOR = timedelta(hours=6)


# Which session speaks for a workspace: the ones asking for a human first, then
# the ones still moving, and only then the ones that have finished.
STATE_PRIORITY = {"done": 1, "working": 2, "failed": 3, "needs_input": 4}

# States that mean the workspace has not wrapped up yet.
LIVE_STATES = frozenset({"working", "needs_input"})

# Branch names shared by every workspace of a repository, so they identify none
# of them.
GENERIC_BRANCHES = frozenset({"main", "master"})

# How long a queued attention overlay stays worth delivering. Alerts are drained
# before the push, so a device that is merely slow used to destroy them; they are
# put back on failure instead. Not forever, though -- replaying "waiting" from
# half an hour ago after a long outage is noise, which is what the old
# drop-everything behaviour was reaching for.
ALERT_RETRY_FOR = 120.0


def _workspace_still_busy(agent: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """Whether any session in the same workspace is still live.

    Only asked about a session that just finished, so the session itself can
    never be the one that answers yes.
    """
    workspace = workspace_key(agent)
    # Through the same filter: an abandoned session left mid-work would otherwise
    # suppress the alert for work that really did finish.
    return any(
        workspace_key(other) == workspace and str(other.get("state") or "") in LIVE_STATES
        for other in _current_sessions(snapshot.get("agents", []))
    )


def _shorten(text: str, budget: int) -> str:
    """Drop the middle of an over-long label instead of its tail.

    A branch is identified by its front and told apart from its siblings by its
    back, so ``verify-local-agent-hub-status`` and its ``-v1`` variant have to
    keep both ends to stay distinct in fifteen columns. The odd character goes
    to the front, which carries more meaning. The gap is two ASCII dots because
    the firmware font has no ellipsis glyph.
    """
    if len(text) <= budget:
        return text
    if budget <= 2:
        return text[:budget]
    keep = budget - 2
    head = (keep + 1) // 2
    return text[:head] + ".." + text[len(text) - (keep - head) :]


def _ascii_label(value: Any, fallback: str = "agent", budget: int = MAX_DEVICE_LABEL) -> str:
    text = "".join(char for char in str(value or "") if " " <= char <= "~")
    text = " ".join(text.split())
    return _shorten(text or fallback, budget)


def _branch_label(agent: Dict[str, Any]) -> str:
    """The branch, minus the conventional type prefix.

    Conductor names a workspace after its branch with that prefix dropped, so
    ``fix/public-error-user-agent`` becomes ``public-error-user-agent``. Match
    that, because the prefix is noise in twenty columns. A branch that names no
    particular work says less than the workspace does, so it yields.
    """
    branch = str(agent.get("branch") or "").rsplit("/", 1)[-1]
    return "" if branch in GENERIC_BRANCHES else branch


def _display_label(agent: Dict[str, Any], budget: int = MAX_DEVICE_LABEL) -> str:
    """Name a workspace by its branch, falling back to the Conductor name.

    ``CONDUCTOR_WORKSPACE_NAME`` is frozen into the agent process environment at
    launch, so a workspace renamed afterwards keeps announcing the codename it
    was created with until a new session replaces it. The branch is re-read from
    git on every event, so it stays current.
    """
    return _ascii_label(
        _branch_label(agent) or agent.get("workspace"), agent.get("agent") or "agent", budget
    )


def _updated(item: Dict[str, Any]) -> Optional[datetime]:
    try:
        stamp = datetime.fromisoformat(str(item.get("updated_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _is_stale(item: Dict[str, Any], now: datetime, older_than: timedelta = COMPLETED_VISIBLE_FOR) -> bool:
    updated = _updated(item)
    # No usable timestamp: treat it as current rather than hide it. A row that
    # never reports a time is a bug worth seeing, not one to swallow.
    return updated is not None and now - updated > older_than



def _current_sessions(agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop sessions that a newer one of the same kind has replaced.

    Conductor runs one agent of a kind per workspace: restarting a chat starts a
    new session id and abandons the old one, which never reports again. An
    abandoned session keeps whatever state it died in -- and a permission prompt
    dies as `needs_input`, which outranks everything, so the workspace stays
    pinned on it forever. Recency settles that; the state ranking cannot, because
    the stale row is exactly the one ranked highest.

    Only within one kind of agent. Claude and Codex genuinely do run side by side
    in a workspace, so neither supersedes the other.
    """
    seen = set()
    current = []
    for item in agents:   # newest first, as the store hands them over
        mark = (workspace_key(item), str(item.get("source") or item.get("agent") or ""))
        if mark in seen:
            continue
        seen.add(mark)
        current.append(item)
    return current


def dashboard_payload(snapshot: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    # A Conductor workspace can hold several sessions at once: Claude restarts
    # under a fresh session id, and Codex runs beside it. The display shows the
    # workspace, so the session that most deserves attention speaks for it.
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in _current_sessions(snapshot.get("agents", [])):
        state = str(item.get("state") or "idle")
        if state == "idle":
            continue
        if state in {"done", "failed"} and _is_stale(item, now):
            continue
        if state in LIVE_STATES and _is_stale(item, now, LIVE_VISIBLE_FOR):
            continue
        key = workspace_key(item)
        current = groups.get(key)
        if current is None:
            groups[key] = item
            order.append(key)
        elif STATE_PRIORITY.get(state, 0) > STATE_PRIORITY.get(str(current.get("state") or ""), 0):
            groups[key] = item
    # How much room a label gets depends on the layout the firmware picks, and
    # that depends on how many rows survive the grouping. So labels are only
    # written once the final row count is known.
    shown = [groups[key] for key in order[:MAX_DEVICE_AGENTS]]
    budget = LAYOUT_LABEL_BUDGET.get(len(shown), MAX_DEVICE_LABEL)
    return {
        "agents": [
            {
                "label": _display_label(item, budget),
                "agent": _ascii_label(item.get("agent"), "agent")[:8].lower(),
                "state": str(item.get("state") or "idle"),
            }
            for item in shown
        ]
    }


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
    # "FAIL " spends five of the alert screen's twenty columns, so the name it
    # introduces is shortened to what is left rather than cut off the end.
    prefix = "FAIL " if state == "failed" else ""
    label = prefix + _display_label(agent, MAX_DEVICE_LABEL - len(prefix))
    return {"state": notify_state, "ttl": 20, "label": label}


class DeviceNotifier:
    """Coalesce snapshots and push them without delaying coding-agent hooks."""

    # 1.5 s was under the device's measured worst-case response (~4 s): the
    # single-threaded firmware legitimately spends seconds rendering a frame, and
    # a push abandoned that early reports a healthy device as broken.
    def __init__(self, base_url: str, timeout: float = 6.0, refresh_sec: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.refresh_sec = refresh_sec
        self._condition = threading.Condition()
        self._latest: Optional[Dict[str, Any]] = None
        # (deadline, payload): the deadline is what lets a failed push put an
        # alert back without resurrecting one that is no longer worth showing.
        self._alerts: Deque[tuple] = deque(maxlen=16)
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
                self._alerts.append((time.monotonic() + ALERT_RETRY_FOR, alert))
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
                for _, alert in alerts:
                    self._post("api/notify", alert)
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                with self._condition:
                    self._last_ok = now
                    self._last_error = ""
            except (OSError, HTTPError, URLError) as exc:
                # A later event or the 30-second refresh retries the current
                # dashboard. The alerts go back at the front of the queue so a
                # device that was briefly busy still gets them -- but only while
                # they are recent, because replaying an old overlay after a long
                # outage says nothing useful about now.
                keep = [item for item in alerts if item[0] > time.monotonic()]
                with self._condition:
                    if keep:
                        self._alerts.extendleft(reversed(keep))
                    self._last_error = str(exc)[:160]
