"""Non-blocking hook adapter for Claude Code and Codex."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .events import ACTIVITY_EVENTS


ACTIVITY_THROTTLE_SEC = 10.0
STAMP_TTL_SEC = 3600.0

# Upper bound on the offline queue. Only a server start drains it, so a stopped
# bridge would otherwise let it grow for as long as agents keep running.
SPOOL_MAX_BYTES = 5 * 1024 * 1024


def claim_activity_slot(stamp_path: Path, now: float, interval: float = ACTIVITY_THROTTLE_SEC) -> bool:
    """Report whether this activity event may be sent, and record that it was.

    A tool event fires far more often than the display can use, so one per
    session per interval is enough to keep a working session looking busy.
    """
    try:
        if now - stamp_path.stat().st_mtime < interval:
            return False
    except OSError:
        pass
    try:
        stamp_path.parent.mkdir(parents=True, exist_ok=True)
        stamp_path.touch()
        os.utime(stamp_path, (now, now))
        _forget_dead_sessions(stamp_path.parent, now)
    except OSError:
        # Hooks must never break the coding agent. Losing the throttle is
        # cheaper than losing the event.
        return True
    return True


def _forget_dead_sessions(stamp_dir: Path, now: float) -> None:
    for stamp in stamp_dir.glob("activity-*.stamp"):
        try:
            if now - stamp.stat().st_mtime > STAMP_TTL_SEC:
                stamp.unlink()
        except OSError:
            continue


def activity_stamp_path(spool_path: Path, source: str, session_id: str) -> Path:
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in session_id) or "unknown"
    return spool_path.parent / f"activity-{source}-{safe}.stamp"


def default_spool_path() -> Path:
    configured = os.environ.get("DESK_HUB_SPOOL")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library" / "Caches" / "GeekMagicDeskHub" / "pending.jsonl"


def post_event(url: str, token: str, envelope: Dict[str, Any], timeout: float = 0.8) -> bool:
    # urllib costs about half this process's start-up, and a throttled tool
    # event never gets here, so it is imported only when something is sent.
    from urllib.request import Request, urlopen

    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except OSError:
        return False


def _trim_spool(path: Path) -> None:
    """Drop the oldest half of the spool once it is over the cap.

    Halving rather than trimming to the line keeps this off the hot path: it
    runs once every few thousand events instead of on every append. The oldest
    events are the ones to lose -- the display only ever shows current state, so
    a replayed hour-old event is overwritten by the next one anyway.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return
    keep = lines[len(lines) // 2 :]
    # Per-process name: hooks from several agents can reach this at the same
    # time, and a shared scratch file would let two of them interleave writes
    # and then publish the mixture. os.replace is atomic, so the worst a race
    # can now cost is one trim overwriting another's.
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.trim")
    try:
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def spool_event(path: Path, envelope: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        # Only the server start drains this, so with the bridge stopped it grows
        # for as long as agents keep running. It lives in a cache directory and
        # nothing else bounds it.
        if path.stat().st_size > SPOOL_MAX_BYTES:
            _trim_spool(path)
    except OSError:
        # Hooks must never break or delay the coding agent.
        pass


def minimize_for_spool(source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep lifecycle metadata offline without caching prompts or responses."""
    common_keys = {
        "cwd",
        "session_id",
        "hook_event_name",
        "type",
        "thread-id",
        "thread_id",
        "turn-id",
        "turn_id",
        "notification_type",
        "error",
        "task_id",
        "team_name",
        "teammate_name",
        "_desk_hub_conductor",
    }
    return {key: value for key, value in payload.items() if key in common_keys}


def load_forward_argv(path: Optional[str]) -> List[str]:
    if not path:
        return []
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    argv = data.get("argv") if isinstance(data, dict) else None
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return []
    return argv


def forward_codex(argv: List[str], raw_payload: str) -> None:
    if not argv:
        return
    import subprocess

    try:
        subprocess.run(
            [*argv, raw_payload],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a Claude/Codex event to the local desk hub")
    parser.add_argument("source", choices=("claude", "codex"))
    parser.add_argument("--url", default=os.environ.get("DESK_HUB_URL", "http://127.0.0.1:4747/api/v1/events"))
    parser.add_argument("--token", default=os.environ.get("DESK_HUB_TOKEN", ""))
    parser.add_argument("--spool", default=str(default_spool_path()))
    parser.add_argument("--forward-config")
    parser.add_argument(
        "--allow-non-conductor",
        action="store_true",
        default=os.environ.get("DESK_HUB_CONDUCTOR_ONLY", "1") == "0",
        help="also collect sessions not launched by a local Conductor workspace",
    )
    parser.add_argument("payload", nargs="?")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    # Codex feeds its notify command the payload as an argument and its hooks on
    # stdin, so the presence of the argument is what tells the two apart.
    use_argv = args.source == "codex" and args.payload is not None
    raw_payload = args.payload if use_argv else sys.stdin.read()
    forward_argv = load_forward_argv(args.forward_config) if use_argv else []
    try:
        payload = json.loads(raw_payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        is_local_conductor = os.environ.get("CONDUCTOR_IS_LOCAL") == "1"
        if not is_local_conductor and not args.allow_non_conductor:
            return 0
        if args.source == "claude" and payload.get("hook_event_name") in ACTIVITY_EVENTS:
            stamp = activity_stamp_path(
                Path(args.spool).expanduser(), args.source, str(payload.get("session_id") or "")
            )
            if not claim_activity_slot(stamp, time.time()):
                return 0
        payload = dict(payload)
        payload["_desk_hub_conductor"] = {
            "is_local": os.environ.get("CONDUCTOR_IS_LOCAL", ""),
            "workspace_name": os.environ.get("CONDUCTOR_WORKSPACE_NAME", ""),
            "workspace_path": os.environ.get("CONDUCTOR_WORKSPACE_PATH", ""),
            "root_path": os.environ.get("CONDUCTOR_ROOT_PATH", ""),
        }
        envelope = {"source": args.source, "payload": payload}
        if not post_event(args.url, args.token, envelope):
            spool_event(
                Path(args.spool).expanduser(),
                {"source": args.source, "payload": minimize_for_spool(args.source, payload)},
            )
    except (json.JSONDecodeError, ValueError):
        pass
    finally:
        # Codex supports one notify program. Preserve any program that was
        # configured before desk-hub installation by forwarding the raw JSON.
        if use_argv:
            forward_codex(forward_argv, raw_payload or "{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
