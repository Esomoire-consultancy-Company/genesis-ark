"""GWIEP R0.7 loopback-only WSGI boundary for synthetic integration tests.

No runner, route binding, credential issuance, or external host is enabled by
this module. Use only behind a trusted test harness listening on loopback.
Production HTTP deployment requires reviewed ingress and real DigitalMe SSO.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Callable, Mapping

from genesis_control_plane.work_api import ApiRequest, WorkStagingAPI, MAX_BYTES

_HOST = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?$")
_LOOPBACK = frozenset({"127.0.0.1", "::1"})


class WorkLoopbackWSGI:
    """Explicit *synthetic* WSGI transport, denies non-local clients.

    Caller must configure an ephemeral loopback socket and a mock issuer.
    WSGI alone does not preserve duplicate raw HTTP headers, so do not expose
    to an external reverse proxy without ingress-level header validation.
    """

    def __init__(self, api: WorkStagingAPI, *,
                 clock: Callable[[], datetime] | None = None):
        self.api = api
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _send(start_response, code: int, data: dict, headers: Mapping[str, str] | None = None):
        body = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        safe = {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
        if headers:
            safe.update(headers)
        safe["Content-Length"] = str(len(body))
        start_response(f"{code} {HTTPStatus(code).phrase}", list(safe.items()))
        return [body]

    def __call__(self, environ, start_response):
        # No unapproved listening address may act as the staging transport.
        if (environ.get("REMOTE_ADDR") not in _LOOPBACK or
            not _HOST.fullmatch(str(environ.get("HTTP_HOST", "")))):
            return self._send(start_response, 403, {"error": "R07_LOOPBACK_ONLY"})
        if environ.get("wsgi.url_scheme") != "http":
            return self._send(start_response, 403, {"error": "R07_TEST_SCHEME_ONLY"})
        if environ.get("HTTP_TRANSFER_ENCODING"):
            return self._send(start_response, 400, {"error": "R07_TRANSFER_ENCODING_DENIED"})
        method = environ.get("REQUEST_METHOD", "")
        if method not in {"GET", "POST"}:
            return self._send(start_response, 405, {"error": "R07_METHOD_DENIED"})
        raw_length = environ.get("CONTENT_LENGTH", "")
        if method == "POST":
            if not isinstance(raw_length, str) or not raw_length.isdecimal():
                return self._send(start_response, 411, {"error": "R07_LENGTH_REQUIRED"})
            if len(raw_length) > 7 or int(raw_length) > MAX_BYTES:
                return self._send(start_response, 413, {"error": "R07_PAYLOAD_TOO_LARGE"})
        elif raw_length not in ("", "0", None):
            return self._send(start_response, 400, {"error": "R07_GET_BODY_DENIED"})
        try:
            length = int(raw_length) if method == "POST" else 0
            stream = environ.get("wsgi.input")
            if stream is None:
                return self._send(start_response, 400, {"error": "R07_INPUT_MISSING"})
            data = stream.read(length)
            if not isinstance(data, bytes) or len(data) != length:
                return self._send(start_response, 400, {"error": "R07_TRUNCATED_BODY"})
            headers = {}
            for key, value in environ.items():
                if key.startswith("HTTP_"):
                    name = key[5:].replace("_", "-").lower()
                    headers[name] = value
            if environ.get("CONTENT_TYPE"):
                headers["content-type"] = environ["CONTENT_TYPE"]
            # WSGI path comes decoded; reject extra path fragments and a
            # query string, keeping R0.6 exact route matching intact.
            if environ.get("QUERY_STRING") or environ.get("SCRIPT_NAME"):
                return self._send(start_response, 400, {"error": "R07_QUERY_DENIED"})
            response = self.api.handle(ApiRequest(
                method=method, path=environ.get("PATH_INFO", ""),
                headers=headers, body=data), now=self.clock())
            return self._send(start_response, response.status,
                              response.body, response.headers)
        except (OSError, ValueError, TypeError):
            # Deliberately avoid publishing anything from the exception, which
            # may contain source packet contents or bearer credentials.
            return self._send(start_response, 400, {"error": "R07_TRANSPORT_DENIED"})
