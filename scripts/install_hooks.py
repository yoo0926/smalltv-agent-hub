#!/usr/bin/env python3
"""Safely add global Claude hooks and chain the existing Codex notify command."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CLAUDE_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "Notification",
    "TaskCreated",
    "TaskCompleted",
    "SubagentStart",
    "Stop",
    "StopFailure",
    "SessionEnd",
)

# Codex fires the same hook events under the same names, and its payloads use
# Claude's field names too. Its `notify` command only speaks when a turn ends,
# so on its own the display could never show Codex working — it sat on the last
# "done" until that aged off. PermissionRequest is Codex-only and is the one
# that matters most: it blocks until a human answers.
CODEX_HOOK_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PermissionRequest",
    "SubagentStart",
    "Stop",
    "SessionEnd",
)

# Deliberately absent: "PostToolUse". The bridge understands it (see
# geekmagic_hub.events.ACTIVITY_EVENTS) and the hook adapter throttles it to one
# send per session per ten seconds, which returns a session to "working" when it
# resumes without a new prompt -- after a permission grant, for example. It is
# not installed because the hook process starts on every single tool call and
# costs about 80 ms each time, whether or not the throttle lets the event
# through. Add it back here if a stale "done" or "needs_input" row is worth that.


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _is_desk_hub_claude(command: Any) -> bool:
    return (
        isinstance(command, str)
        and "desk-hub-event" in command
        and command.rstrip().endswith(" claude")
    )


def merge_claude_hooks(settings: Dict[str, Any], command: str) -> Tuple[int, int]:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Claude settings 'hooks' must be an object")
    added = 0
    updated = 0
    for event in CLAUDE_EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Claude hook '{event}' must be an array")
        exists = False
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_hooks = group.get("hooks", [])
            if not isinstance(group_hooks, list):
                continue
            for hook in group_hooks:
                if not isinstance(hook, dict):
                    continue
                existing = hook.get("command")
                if existing == command:
                    exists = True
                    break
                # A clone moved to another directory. Update the old absolute
                # desk-hub path in place instead of leaving a broken hook and
                # appending a second invocation.
                if _is_desk_hub_claude(existing):
                    hook["command"] = command
                    updated += 1
                    exists = True
                    break
            if exists:
                break
        if not exists:
            groups.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
            added += 1
    return added, updated


def _is_desk_hub_codex(command: Any) -> bool:
    return isinstance(command, str) and "desk-hub-event" in command and " codex" in command


def merge_codex_hooks(hooks_doc: Dict[str, Any], command: str) -> Tuple[int, int]:
    """Add the desk-hub hook to Codex's hooks.json without disturbing anything else.

    Other tools already own entries here, so every event keeps whatever groups it
    has and only gains one more. A desk-hub entry left over from a clone at a
    different path is rewritten in place rather than duplicated.
    """
    hooks = hooks_doc.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Codex hooks.json 'hooks' must be an object")
    added = 0
    updated = 0
    for event in CODEX_HOOK_EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Codex hook '{event}' must be an array")
        exists = False
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_hooks = group.get("hooks", [])
            if not isinstance(group_hooks, list):
                continue
            for hook in group_hooks:
                if not isinstance(hook, dict):
                    continue
                existing = hook.get("command")
                if existing == command:
                    exists = True
                    break
                if _is_desk_hub_codex(existing):
                    hook["command"] = command
                    updated += 1
                    exists = True
                    break
            if exists:
                break
        if not exists:
            groups.append({"hooks": [{"type": "command", "command": command}]})
            added += 1
    return added, updated


def add_claude_hooks(settings: Dict[str, Any], command: str) -> int:
    """Backward-compatible helper used by callers that only need add count."""
    added, _ = merge_claude_hooks(settings, command)
    return added


NOTIFY_KEY = re.compile(r"(?m)^notify\s*=")
NOTIFY_ASSIGNMENT = re.compile(r"(?ms)^notify\s*=\s*(\[.*?\])[^\S\n]*$")


def parse_notify(config: str) -> Tuple[Optional[List[str]], Optional[re.Match]]:
    # The array may span several lines, so the closing bracket is matched
    # lazily instead of being pinned to the line that opens it.
    match = NOTIFY_ASSIGNMENT.search(config)
    if not match:
        return None, None
    raw = match.group(1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(raw)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Codex notify must be an array of strings")
    return parsed, match


def replace_notify(config: str, argv: List[str]) -> str:
    line = "notify = " + json.dumps(argv, ensure_ascii=False)
    _, match = parse_notify(config)
    if match:
        return config[: match.start()] + line + config[match.end() :]
    if NOTIFY_KEY.search(config):
        # Prepending here would leave two top-level ``notify`` keys, which makes
        # the whole Codex config unparseable.
        raise ValueError("Codex notify exists but could not be parsed; refusing to duplicate it")
    return line + "\n" + config


def rewrite_desk_hub_notify(
    argv: List[str], hook: str, forward_path: str
) -> Tuple[List[str], bool]:
    """Refresh desk-hub paths inside a possibly nested notify chain.

    Codex integrations can wrap the previous notifier as a JSON-encoded argv
    string (for example a ``--previous-notify`` argument). Walk those lists so
    moving the clone does not append a duplicate or leave an absolute old path.
    """
    out = list(argv)
    direct = False
    found = False

    for index, item in enumerate(out):
        if isinstance(item, str) and item.rstrip("/").endswith("/bin/desk-hub-event"):
            out[index] = hook
            direct = found = True

    for index, item in enumerate(out):
        if not isinstance(item, str) or not item.lstrip().startswith("["):
            continue
        try:
            nested = json.loads(item)
        except json.JSONDecodeError:
            continue
        if not isinstance(nested, list) or not all(isinstance(value, str) for value in nested):
            continue
        rewritten, nested_found = rewrite_desk_hub_notify(nested, hook, forward_path)
        if nested_found:
            if rewritten != nested:
                out[index] = json.dumps(
                    rewritten, ensure_ascii=False, separators=(",", ":")
                )
            found = True

    if direct:
        for index, item in enumerate(out[:-1]):
            if item == "--forward-config":
                out[index + 1] = forward_path

    return out, found


def backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(path.name + f".desk-hub-backup-{suffix}")
    shutil.copy2(path, destination)
    return destination


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    project_dir = Path(__file__).resolve().parents[1]
    default_hook = project_dir / "bin" / "desk-hub-event"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes; otherwise print a dry run")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--hook", type=Path, default=default_hook)
    parser.add_argument("--skip-claude", action="store_true")
    parser.add_argument("--skip-codex", action="store_true")
    args = parser.parse_args()

    hook = args.hook.expanduser().resolve()
    runtime_dir = project_dir / ".runtime"
    forward_path = runtime_dir / "codex-forward.json"
    actions: List[str] = []

    claude_path = args.home / ".claude" / "settings.json"
    claude_settings: Dict[str, Any] = {}
    if not args.skip_claude:
        claude_settings = load_json(claude_path)
        added, updated = merge_claude_hooks(
            claude_settings, f"{shlex.quote(str(hook))} claude"
        )
        actions.append(
            f"Claude: add {added}, update {updated} hooks in {claude_path}"
        )

    codex_path = args.home / ".codex" / "config.toml"
    codex_hooks_path = args.home / ".codex" / "hooks.json"
    codex_hooks_doc: Dict[str, Any] = {}
    codex_config = ""
    new_codex_config = ""
    forward_argv: Optional[List[str]] = None
    if not args.skip_codex:
        codex_config = codex_path.read_text(encoding="utf-8") if codex_path.exists() else ""
        existing, _ = parse_notify(codex_config)
        new_notify = [str(hook), "codex", "--forward-config", str(forward_path)]
        rewritten, contains_hub = rewrite_desk_hub_notify(
            existing or [], str(hook), str(forward_path)
        )
        if contains_hub:
            new_codex_config = replace_notify(codex_config, rewritten)
            if rewritten == existing:
                actions.append("Codex: desk-hub is already present in the notify chain")
            else:
                actions.append("Codex: update moved desk-hub paths in the notify chain")
        else:
            if existing and existing != new_notify:
                forward_argv = existing
                actions.append("Codex: preserve and forward the existing notify command")
            new_codex_config = replace_notify(codex_config, new_notify)
            actions.append(f"Codex: set chained notify in {codex_path}")

        codex_hooks_doc = load_json(codex_hooks_path)
        hooks_added, hooks_updated = merge_codex_hooks(
            codex_hooks_doc, f"{shlex.quote(str(hook))} codex"
        )
        actions.append(
            f"Codex: add {hooks_added}, update {hooks_updated} hooks in {codex_hooks_path}"
        )

    print("\n".join(actions))
    if not args.apply:
        print("Dry run only. Re-run with --apply to write changes.")
        return 0

    backups: List[Path] = []
    if not args.skip_claude:
        saved = backup(claude_path)
        if saved:
            backups.append(saved)
        write_text(claude_path, json.dumps(claude_settings, ensure_ascii=False, indent=2) + "\n")
    if not args.skip_codex:
        saved = backup(codex_path)
        if saved:
            backups.append(saved)
        write_text(codex_path, new_codex_config)
        saved = backup(codex_hooks_path)
        if saved:
            backups.append(saved)
        write_text(codex_hooks_path, json.dumps(codex_hooks_doc, ensure_ascii=False, indent=2) + "\n")
        if forward_argv:
            write_text(forward_path, json.dumps({"argv": forward_argv}, ensure_ascii=False, indent=2) + "\n")

    for saved in backups:
        print(f"Backup: {saved}")
    print("Hook installation complete. Restart new Claude/Codex sessions in Conductor before testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
