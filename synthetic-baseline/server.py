"""Local-only, synthetic decision simulator. Not a live API or authentication server.

Use `python3 synthetic-baseline/server.py` and run isolated tests against the
loopback address. It intentionally does not accept any non-loopback binding.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock

from engine import SyntheticOracle, load_manifest

ROOT = Path(__file__).resolve().parent
WORKBENCH = ROOT / "workbench"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/workbench.css": ("workbench.css", "text/css; charset=utf-8"),
    "/workbench.js": ("workbench.js", "text/javascript; charset=utf-8"),
}

HOST = "127.0.0.1"
PORT = 4178
MAX_BODY = 4096


class SandboxHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    oracle: SyntheticOracle
    lock: Lock

    def log_message(self, *_args) -> None:
        # No personal data, request bodies or identifiers are logged.
        return

    def reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def static_response(self, filename: str, content_type: str) -> None:
        data = (WORKBENCH / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path in STATIC_ROUTES:
            return self.static_response(*STATIC_ROUTES[self.path])
        if self.path == "/health":
            return self.reply(200, {
                "status": "OK_SYNTHETIC", "synthetic": True,
                "executable": False, "fixture_id": self.oracle.manifest["fixture_id"]
            })
        if self.path == "/catalog":
            m = self.oracle.manifest
            return self.reply(200, {
                "synthetic": True, "executable": False,
                "actors": [{"id": a["id"], "role": a["role"], "state": a["state"]}
                           for a in m["actors"]],
                "organizations": m["organizations"],
                "memberships": m["memberships"],
                "representations": m["representations"],
                "licences": m["licences"],
                "actions": [p["action"] for p in m["action_policies"]],
            })
        if self.path == "/scenarios":
            scenarios = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
            return self.reply(200, {"synthetic": True, "executable": False,
                                    "scenarios": scenarios})
        return self.reply(404, {"error": "NOT_FOUND", "synthetic": True})

    def do_POST(self) -> None:
        if self.path != "/simulate":
            return self.reply(404, {"error": "NOT_FOUND", "synthetic": True})
        ctype = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            return self.reply(415, {"error": "JSON_REQUIRED", "synthetic": True})
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 1 or length > MAX_BODY:
            return self.reply(413, {"error": "INVALID_BODY_LENGTH", "synthetic": True})
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw.decode("utf-8"))
            with self.lock:
                receipt = self.oracle.evaluate(request)
        except (ValueError, UnicodeDecodeError, TypeError):
            return self.reply(400, {"error": "INVALID_SYNTHETIC_REQUEST", "synthetic": True,
                                    "executable": False})
        return self.reply(200, receipt)


def make_server(port: int = PORT) -> ThreadingHTTPServer:
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("invalid local port")
    # Bind to loopback only. Do not add an environment-controlled host override.
    cls = type("BoundSandboxHandler", (SandboxHandler,), {
        "oracle": SyntheticOracle(load_manifest()), "lock": Lock()
    })
    return ThreadingHTTPServer((HOST, port), cls)


if __name__ == "__main__":
    # Local demo deliberately requires explicit command; CI only instantiates
    # an ephemeral server inside unit tests, not a standing daemon.
    with make_server() as server:
        print(f"SYNTHETIC sandbox only: http://{HOST}:{server.server_port} (Ctrl-C to stop)")
        print("NO real accounts, licensing, execution or payments")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
