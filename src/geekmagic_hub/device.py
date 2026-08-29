"""Asynchronous push client for the SmallTV Agent Hub firmware."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


MAX_DEVICE_AGENTS = 4
MAX_DEVICE_LABEL = 20
COMPLETED_VISIBLE_FOR = timedelta(minutes=30)


def _ascii_label(value: Any, fallback: str = "agent") -> str:
    text = "".join(char for char in str(value or "") if " " <= char <= "~")
    text = " ".join(text.split())
    return (text or fallback)[:MAX_DEVICE_LABEL]


def dashboard_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    now = datetime.now(timezone.utc)
    for item in snapshot.get("agents", []):
        state = str(item.get("state") or "idle")
        if state == "idle":
            continue
        if state in {"done", "failed"}:
            try:
                updated = datetime.fromisoformat(str(item.get("updated_at") or "").replace("Z", "+00:00"))
            except ValueError:
                updated = now
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if now - updated > COMPLETED_VISIBLE_FOR:
                continue
        rows.append(
            {
                "label": _ascii_label(item.get("workspace"), item.get("agent") or "agent"),
                "agent": _ascii_label(item.get("agent"), "agent")[:8].lower(),
                "state": state,
            }
        )
        if len(rows) >= MAX_DEVICE_AGENTS:
            break
    return {"agents": rows}


def alert_payload(agent: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not agent:
        return None
    state = str(agent.get("state") or "")
    if state == "done":
        notify_state = "done"
    elif state in {"needs_input", "failed"}:
        notify_state = "waiting"
    else:
        return None
    label = _ascii_label(agent.get("workspace"), agent.get("agent") or "agent")
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
        alert = alert_payload(changed_agent)
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
