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


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def add_claude_hooks(settings: Dict[str, Any], command: str) -> int:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Claude settings 'hooks' must be an object")
    added = 0
    for event in CLAUDE_EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Claude hook '{event}' must be an array")
        exists = any(
            isinstance(group, dict)
            and any(
                isinstance(hook, dict) and hook.get("command") == command
                for hook in group.get("hooks", [])
            )
            for group in groups
        )
        if not exists:
            groups.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
            added += 1
    return added


def parse_notify(config: str) -> Tuple[Optional[List[str]], Optional[re.Match]]:
    match = re.search(r"(?m)^notify\s*=\s*(\[[^\n]*\])\s*$", config)
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
    return line + "\n" + config


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
        added = add_claude_hooks(claude_settings, f"{shlex.quote(str(hook))} claude")
        actions.append(f"Claude: add {added} hooks in {claude_path}")

    codex_path = args.home / ".codex" / "config.toml"
    codex_config = ""
    new_codex_config = ""
    forward_argv: Optional[List[str]] = None
    if not args.skip_codex:
        codex_config = codex_path.read_text(encoding="utf-8") if codex_path.exists() else ""
        existing, _ = parse_notify(codex_config)
        new_notify = [str(hook), "codex", "--forward-config", str(forward_path)]
        if existing and existing != new_notify and str(hook) not in existing:
            forward_argv = existing
            actions.append("Codex: preserve and forward the existing notify command")
        new_codex_config = replace_notify(codex_config, new_notify)
        actions.append(f"Codex: set chained notify in {codex_path}")

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
        if forward_argv:
            write_text(forward_path, json.dumps({"argv": forward_argv}, ensure_ascii=False, indent=2) + "\n")

    for saved in backups:
        print(f"Backup: {saved}")
    print("Hook installation complete. Restart new Claude/Codex sessions in Conductor before testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
