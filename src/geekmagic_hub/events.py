"""Normalize Claude Code and Codex notifications into one small state model."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _git_value(cwd: str, *args: str) -> str:
    if not cwd or not Path(cwd).is_dir():
        return ""
    # Imported here so the hook process, which reads this module only for
    # ACTIVITY_EVENTS, does not pay for subprocess on every tool call.
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _workspace_context(cwd: str, payload: Dict[str, Any]) -> Dict[str, str]:
    conductor = payload.get("_desk_hub_conductor")
    if not isinstance(conductor, dict):
        conductor = {}
    root = _git_value(cwd, "rev-parse", "--show-toplevel")
    branch = _git_value(cwd, "branch", "--show-current")
    workspace_path = str(conductor.get("workspace_path") or root or cwd)
    workspace = str(conductor.get("workspace_name") or (Path(workspace_path).name if workspace_path else "unknown"))
    return {
        "cwd": cwd,
        "workspace": workspace,
        "workspace_path": workspace_path,
        "root_path": str(conductor.get("root_path") or root),
        "branch": branch,
        "conductor_local": str(conductor.get("is_local") or "") == "1",
    }


# Events that only prove a session is still moving. Stop fires at the end of
# every turn, but a session can resume without a new prompt, so these bring a
# finished session back to "working".
ACTIVITY_EVENTS = frozenset({"PostToolUse"})


def _claude_state(event: str, payload: Dict[str, Any]) -> Optional[str]:
    if event in {"SessionStart"}:
        return "idle"
    if event in ACTIVITY_EVENTS or event in {"UserPromptSubmit", "SubagentStart", "TaskCreated"}:
        return "working"
    if event == "Stop":
        return "done"
    if event == "StopFailure":
        return "failed"
    if event == "SessionEnd":
        return "idle"
    if event == "Notification":
        notification_type = str(payload.get("notification_type", "")).lower()
        message = str(payload.get("message", "")).lower()
        if (
            "permission" in notification_type
            or "idle_prompt" in notification_type
            or "permission" in message
            or "input" in message
        ):
            return "needs_input"
    # TaskCompleted may describe one subtask, not the whole session. Keep the
    # current state and expose it as activity instead of claiming the turn ended.
    return None


def _claude_message(event: str, payload: Dict[str, Any]) -> str:
    if event == "UserPromptSubmit" or event in ACTIVITY_EVENTS:
        return "Working"
    if event == "Stop":
        return "Turn complete"
    if event == "StopFailure":
        return _text(payload.get("error") or "Turn failed")
    if event == "Notification":
        notification_type = str(payload.get("notification_type") or "")
        if notification_type == "permission_prompt":
            return "Permission required"
        if notification_type == "idle_prompt":
            return "Waiting for input"
        return "Notification"
    if event == "TaskCreated":
        return "Task started"
    if event == "TaskCompleted":
        return "Task completed"
    return _text(event)


def normalize_event(source: str, payload: Dict[str, Any], received_at: Optional[str] = None) -> Dict[str, Any]:
    """Return a normalized event suitable for the state store and ESP32 API."""
    source = source.lower().strip()
    cwd = str(payload.get("cwd") or "")
    context = _workspace_context(cwd, payload)

    if source == "claude":
        event = str(payload.get("hook_event_name") or payload.get("event") or "unknown")
        session_id = str(payload.get("session_id") or "")
        state = _claude_state(event, payload)
        message = _claude_message(event, payload)
        agent = "claude"
    elif source == "codex":
        event = str(payload.get("type") or payload.get("event") or "unknown")
        session_id = str(payload.get("thread-id") or payload.get("thread_id") or "")
        state = "done" if event == "agent-turn-complete" else None
        message = "Turn complete" if event == "agent-turn-complete" else _text(event)
        agent = "codex"
    else:
        event = str(payload.get("event") or "unknown")
        session_id = str(payload.get("session_id") or "")
        state = payload.get("state")
        message = _text(payload.get("message") or event)
        agent = str(payload.get("agent") or source or "unknown")

    if not session_id:
        basis = f"{source}:{cwd or context['workspace']}"
        session_id = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    return {
        "id": hashlib.sha256(
            f"{source}:{session_id}:{event}:{payload.get('turn-id', '')}:{received_at or ''}".encode("utf-8")
        ).hexdigest()[:20],
        "source": source,
        "agent": agent,
        "session_id": session_id,
        "session_key": f"{source}:{session_id}",
        "event": event,
        "state": state,
        "message": message,
        "received_at": received_at or utc_now(),
        **context,
        "details": {
            "turn_id": payload.get("turn-id") or payload.get("turn_id"),
            "task_id": payload.get("task_id"),
            "task_subject": payload.get("task_subject"),
            "notification_type": payload.get("notification_type"),
            "error": payload.get("error"),
        },
    }
