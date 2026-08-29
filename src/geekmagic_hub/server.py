"""Small dependency-free HTTP bridge consumed by the GeekMagic firmware."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .device import DeviceNotifier
from .store import StateStore


def default_spool_path() -> Path:
    configured = os.environ.get("DESK_HUB_SPOOL")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library" / "Caches" / "GeekMagicDeskHub" / "pending.jsonl"


def replay_spool(store: StateStore, spool_path: Path) -> int:
    """Atomically consume queued hook events left while the server was down."""
    if not spool_path.exists():
        return 0
    spool_path.parent.mkdir(parents=True, exist_ok=True)
    fd, processing_name = tempfile.mkstemp(prefix="pending-", suffix=".processing", dir=str(spool_path.parent))
    os.close(fd)
    processing_path = Path(processing_name)
    processing_path.unlink()
    try:
        os.replace(spool_path, processing_path)
    except FileNotFoundError:
        return 0

    accepted = 0
    rejected = []
    try:
        for line in processing_path.read_text(encoding="utf-8").splitlines():
            try:
                envelope = json.loads(line)
                source = str(envelope.get("source") or "")
                payload = envelope.get("payload")
                if not source or not isinstance(payload, dict):
                    raise ValueError("invalid envelope")
                store.apply(source, payload)
                accepted += 1
            except (json.JSONDecodeError, ValueError, OSError):
                rejected.append(line)
        if rejected:
            with spool_path.open("a", encoding="utf-8") as handle:
                for line in rejected:
                    handle.write(line + "\n")
    finally:
        try:
            processing_path.unlink()
        except FileNotFoundError:
            pass
    return accepted


class DeskHubServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple,
        store: StateStore,
        token: str = "",
        notifier: Optional[DeviceNotifier] = None,
    ) -> None:
        self.store = store
        self.token = token
        self.notifier = notifier
        super().__init__(address, DeskHubHandler)

    def server_close(self) -> None:
        if self.notifier:
            self.notifier.close()
        super().server_close()


class DeskHubHandler(BaseHTTPRequestHandler):
    server: DeskHubServer

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _authorized(self) -> bool:
        if not self.server.token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {self.server.token}"

    def _json(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            device = self.server.notifier.status() if self.server.notifier else {"configured": False}
            self._json(200, {"ok": True, "device": device})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        if parsed.path == "/api/v1/status":
            self._json(200, self.server.store.snapshot())
            return
        if parsed.path == "/api/v1/events":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                limit = 100
            self._json(200, {"events": self.server.store.events(limit)})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/api/v1/events":
            self._json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 1024 * 1024:
            self._json(400, {"error": "invalid_content_length"})
            return
        try:
            envelope = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "invalid_json"})
            return
        source = str(envelope.get("source") or "")
        payload = envelope.get("payload")
        if not source or not isinstance(payload, dict):
            self._json(400, {"error": "expected_source_and_payload"})
            return
        agent = self.server.store.apply(source, payload)
        if self.server.notifier:
            self.server.notifier.publish(self.server.store.snapshot(), agent)
        self._json(202, {"accepted": True, "agent": agent})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GeekMagic local Conductor status bridge")
    parser.add_argument("--host", default=os.environ.get("DESK_HUB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DESK_HUB_PORT", "4747")))
    parser.add_argument("--token", default=os.environ.get("DESK_HUB_TOKEN", ""))
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("DESK_HUB_DATA_DIR", ".runtime")))
    parser.add_argument("--spool", type=Path, default=default_spool_path())
    parser.add_argument("--device-url", default=os.environ.get("DESK_HUB_DEVICE_URL", ""))
    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    store = StateStore(args.data_dir.expanduser().resolve())
    replayed = replay_spool(store, args.spool.expanduser())
    notifier = DeviceNotifier(args.device_url) if args.device_url else None
    if notifier:
        notifier.publish(store.snapshot())
    server = DeskHubServer((args.host, args.port), store, args.token, notifier)
    print(f"GeekMagic desk hub listening on http://{args.host}:{args.port}")
    print(f"Status endpoint: http://{args.host}:{args.port}/api/v1/status")
    if notifier:
        print(f"SmallTV push target: {args.device_url.rstrip('/')}")
    if replayed:
        print(f"Replayed {replayed} queued events")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
