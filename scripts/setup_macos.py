#!/usr/bin/env python3
"""Interactively install the desk hub hooks and macOS login service."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit


ENV_KEYS = (
    "DESK_HUB_DEVICE_URL",
    "DESK_HUB_INSTALL_CLAUDE",
    "DESK_HUB_INSTALL_CODEX",
    "DESK_HUB_INSTALL_SERVICE",
)


@dataclass(frozen=True)
class SetupConfig:
    device_url: str
    install_claude: bool
    install_codex: bool
    install_service: bool


def load_env_file(path: Path) -> Dict[str, str]:
    """Read the small, declarative subset of dotenv syntax used by setup."""
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or key not in ENV_KEYS:
            continue
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        if len(parts) > 1:
            raise ValueError(
                f"{path}:{line_number}: quote values containing spaces"
            )
        values[key] = parts[0] if parts else ""
    return values


def parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {value!r}")


def validate_device_url(value: str, required: bool = True) -> str:
    url = value.strip().rstrip("/")
    if not url and not required:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("device URL must look like http://smalltv-xxxx.local")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("device URL must not contain credentials, a query, or a fragment")
    return url


def prompt_text(
    label: str,
    default: str,
    *,
    required: bool,
    input_fn: Callable[[str], str] = input,
) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        try:
            answer = input_fn(f"{label}{suffix}: ").strip()
        except EOFError as exc:
            raise ValueError(
                "interactive input ended; rerun in a terminal or use --non-interactive"
            ) from exc
        value = answer or default
        if value or not required:
            return value
        print("A value is required on the first setup run.")


def prompt_bool(
    label: str,
    default: bool,
    input_fn: Callable[[str], str] = input,
) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        try:
            answer = input_fn(f"{label} [{suffix}]: ").strip()
        except EOFError as exc:
            raise ValueError(
                "interactive input ended; rerun in a terminal or use --non-interactive"
            ) from exc
        if not answer:
            return default
        try:
            return parse_bool(answer, label)
        except ValueError:
            print("Enter y or n, or press Enter to use the default.")


def config_from_values(values: Dict[str, str]) -> SetupConfig:
    install_service = parse_bool(
        values.get("DESK_HUB_INSTALL_SERVICE", "true"),
        "DESK_HUB_INSTALL_SERVICE",
    )
    return SetupConfig(
        device_url=validate_device_url(
            values.get("DESK_HUB_DEVICE_URL", ""), required=install_service
        ),
        install_claude=parse_bool(
            values.get("DESK_HUB_INSTALL_CLAUDE", "true"),
            "DESK_HUB_INSTALL_CLAUDE",
        ),
        install_codex=parse_bool(
            values.get("DESK_HUB_INSTALL_CODEX", "true"),
            "DESK_HUB_INSTALL_CODEX",
        ),
        install_service=install_service,
    )


def prompt_config(
    values: Dict[str, str], input_fn: Callable[[str], str] = input
) -> SetupConfig:
    install_service_default = parse_bool(
        values.get("DESK_HUB_INSTALL_SERVICE", "true"),
        "DESK_HUB_INSTALL_SERVICE",
    )
    install_claude = prompt_bool(
        "Install/update Claude Code hooks",
        parse_bool(
            values.get("DESK_HUB_INSTALL_CLAUDE", "true"),
            "DESK_HUB_INSTALL_CLAUDE",
        ),
        input_fn,
    )
    install_codex = prompt_bool(
        "Install/update Codex notifications",
        parse_bool(
            values.get("DESK_HUB_INSTALL_CODEX", "true"),
            "DESK_HUB_INSTALL_CODEX",
        ),
        input_fn,
    )
    install_service = prompt_bool(
        "Install/start the macOS login service",
        install_service_default,
        input_fn,
    )
    if install_service:
        device_url = prompt_text(
            "SmallTV device URL",
            values.get("DESK_HUB_DEVICE_URL", ""),
            required=True,
            input_fn=input_fn,
        )
    else:
        device_url = values.get("DESK_HUB_DEVICE_URL", "")
    return SetupConfig(
        device_url=validate_device_url(device_url, required=install_service),
        install_claude=install_claude,
        install_codex=install_codex,
        install_service=install_service,
    )


def write_env_file(path: Path, config: SetupConfig) -> None:
    values = {
        "DESK_HUB_DEVICE_URL": config.device_url,
        "DESK_HUB_INSTALL_CLAUDE": str(config.install_claude).lower(),
        "DESK_HUB_INSTALL_CODEX": str(config.install_codex).lower(),
        "DESK_HUB_INSTALL_SERVICE": str(config.install_service).lower(),
    }
    lines = [
        "# Local defaults saved by scripts/setup_macos.sh.",
        "# This file is intentionally ignored by Git.",
    ]
    lines.extend(f"{key}={json.dumps(values[key])}" for key in ENV_KEYS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def build_commands(
    project_dir: Path, python: Path, config: SetupConfig, *, apply: bool
) -> List[List[str]]:
    commands: List[List[str]] = []
    if config.install_claude or config.install_codex:
        hooks = [str(python), str(project_dir / "scripts" / "install_hooks.py")]
        if not config.install_claude:
            hooks.append("--skip-claude")
        if not config.install_codex:
            hooks.append("--skip-codex")
        if apply:
            hooks.append("--apply")
        commands.append(hooks)
    if config.install_service:
        service = [
            str(python),
            str(project_dir / "scripts" / "install_launch_agent.py"),
            "--device-url",
            config.device_url,
        ]
        if apply:
            service.append("--apply")
        commands.append(service)
    return commands


def main(argv: Optional[List[str]] = None) -> int:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=project_dir / ".env",
        help="local defaults file (default: repository .env)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="use environment-file values without prompting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview installers without saving or applying changes",
    )
    args = parser.parse_args(argv)

    example_file = project_dir / ".env.example"
    values = load_env_file(example_file)
    values.update(load_env_file(args.env_file))
    values.update({key: os.environ[key] for key in ENV_KEYS if key in os.environ})

    try:
        if args.non_interactive:
            config = config_from_values(values)
        else:
            print("GeekMagic Desk Hub setup")
            print("Press Enter to accept each value shown in brackets.\n")
            config = prompt_config(values)
    except ValueError as exc:
        parser.error(str(exc))

    python = project_dir / "firmware" / "smalltv-agent-hub" / ".venv" / "bin" / "python"
    if not python.is_file():
        parser.error("build environment not found; run ./scripts/bootstrap_macos.sh --build first")

    if not args.dry_run:
        args.env_file.parent.mkdir(parents=True, exist_ok=True)
        write_env_file(args.env_file, config)
        print(f"Saved local defaults: {args.env_file}")

    commands = build_commands(project_dir, python, config, apply=not args.dry_run)
    if not commands:
        print("No hooks or login service selected; nothing to install.")
        return 0
    for command in commands:
        if args.dry_run:
            print(f"Dry run: {shlex.join(command)}")
        subprocess.run(command, cwd=project_dir, check=True)

    print("Setup dry run complete." if args.dry_run else "Setup complete.")
    if config.install_claude or config.install_codex:
        print("Start new Conductor sessions before testing notifications.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
