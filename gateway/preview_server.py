"""Explicitly opt-in, static-only Genesis Gateway PREVIEW service.

Never mount or serve the Genesis control-plane directory. This preview is not
a privileged gateway, an account provider, a Warden executor or a live Registry.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import os
import sys

ROOT = Path(__file__).resolve().parent
# No directory traversal, directory listing, runtime code, private repository
# documents, environment variables or Python files can be served.
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/portal.js": ("portal.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'none'; object-src 'none'; "
    "form-action 'none'; frame-ancestors 'none'; base-uri 'none'"
)


class StaticPreviewHandler(BaseHTTPRequestHandler):
    server_version = "GenesisPublicPreview/0.1"
    sys_version = ""

    def do_GET(self) -> None:
        self._respond(send_body=True)

    def do_HEAD(self) -> None:
        self._respond(send_body=False)

    def _respond(self, send_body: bool) -> None:
        try:
            path = urlsplit(self.path).path
        except ValueError:
            path = ""

        status = 200
        if path == "/healthz":
            payload = b"healthy:static-preview-only\n"
            mime = "text/plain; charset=utf-8"
        elif path in ASSETS:
            filename, mime = ASSETS[path]
            try:
                payload = (ROOT / filename).read_bytes()
            except OSError:
                status = 503
                payload = b"STATIC_ASSET_UNAVAILABLE\n"
                mime = "text/plain; charset=utf-8"
        else:
            status = 404
            payload = b"NOT_FOUND\n"
            mime = "text/plain; charset=utf-8"

        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Genesis-Deployment-Qualification", "PREVIEW_NOT_ACCEPTED")
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        # No request query strings or client data in these preview logs.
        return


def preview_opted_in(settings: dict[str, str]) -> bool:
    return settings.get("GENESIS_STATIC_PREVIEW_ENABLE") == "true"


def main() -> int:
    if not preview_opted_in(dict(os.environ)):
        print(
            "HOLD: GENESIS_STATIC_PREVIEW_ENABLE=true is required to start "
            "this unqualified public preview.",
            file=sys.stderr,
        )
        return 78
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        print("INVALID_PORT", file=sys.stderr)
        return 78
    if not 1024 <= port <= 65535:
        print("PORT_OUT_OF_ALLOWED_RANGE", file=sys.stderr)
        return 78
    with ThreadingHTTPServer(("0.0.0.0", port), StaticPreviewHandler) as httpd:
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
