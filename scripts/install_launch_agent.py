#!/usr/bin/env python3
"""Install the desk hub as a per-user macOS launchd service."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


LABEL = "com.geekmagic.desk-hub"


def build_plist(project_dir: Path, host: str, port: int, device_url: str = "") -> Dict[str, Any]:
    runtime_dir = project_dir / ".runtime"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(project_dir / "bin" / "desk-hub"),
            "--host",
            host,
            "--port",
            str(port),
            "--data-dir",
            str(runtime_dir),
            "--device-url",
            device_url,
        ],
        "WorkingDirectory": str(project_dir),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(runtime_dir / "desk-hub.stdout.log"),
        "StandardErrorPath": str(runtime_dir / "desk-hub.stderr.log"),
    }


def run_launchctl(arguments: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def main() -> int:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write and load the service")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4747)
    parser.add_argument("--device-url", default=os.environ.get("DESK_HUB_DEVICE_URL", ""))
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()

    target = args.home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{LABEL}"

    if args.uninstall:
        print(f"Unload {service} and remove {target}")
        if not args.apply:
            print("Dry run only. Re-run with --apply to uninstall.")
            return 0
        run_launchctl(["bootout", service], check=False)
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        print("Desk hub launch agent removed.")
        return 0

    plist = build_plist(project_dir, args.host, args.port, args.device_url)
    print(f"Install {LABEL} at {target}")
    print(f"Listen on {args.host}:{args.port}")
    print(f"Push to {args.device_url}")
    if not args.apply:
        print("Dry run only. Re-run with --apply to install and load it.")
        return 0

    runtime_dir = project_dir / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(target.name + f".backup-{suffix}")
        shutil.copy2(target, backup)
        print(f"Backup: {backup}")

    data = plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=False)
    fd, temp_name = tempfile.mkstemp(prefix=f"{LABEL}-", suffix=".plist", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, target)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

    run_launchctl(["bootout", service], check=False)
    run_launchctl(["bootstrap", domain, str(target)])
    run_launchctl(["kickstart", "-k", service])
    print(f"Desk hub launch agent is active: {service}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
