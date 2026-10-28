"""Staging-only private-network acceptance check.

Executes a bounded set of HTTP requests against the deny-only gateway.
No public domain, Docker adapter or database administrator credentials needed.
"""
from __future__ import annotations

import json
import os
import re
from urllib import error, parse, request
from uuid import uuid4


def _send(url: str, *, body: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    payload = None
    method = "GET"
    if body is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body, separators=(",", ":")).encode()
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    req = request.Request(url, data=payload, headers=headers, method=method)
    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # Never forward a bearer token to a redirect target.

    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=8) as resp:
            return resp.status, json.load(resp)
    except error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise RuntimeError("SMOKE_REDIRECT_REJECTED") from None
        return exc.code, json.load(exc)


def main():
    base = os.environ.get("GENESIS_GATEWAY_INTERNAL_URL", "").rstrip("/")
    key = os.environ.get("GENESIS_GATEWAY_API_KEY", "")
    addr = parse.urlparse(base)
    if addr.scheme != "http" or not (addr.hostname or "").endswith(".railway.internal"):
        raise SystemExit("SMOKE_TARGET_NOT_PRIVATE")
    if len(key) < 32:
        raise SystemExit("SMOKE_API_KEY_MISSING")

    def check(ok: bool, code: str) -> None:
        if not ok:
            raise RuntimeError("SMOKE_CHECK_FAILED:" + code)

    check(_send(base + "/healthz")[0] == 200, "HEALTH")
    code, ready = _send(base + "/readyz")
    check(code == 200 and ready.get("execution_enabled") is False, "READINESS")
    check(ready.get("mode") == "deny-only", "DENY_ONLY")

    intent = {
        "request_id": str(uuid4()),
        "correlation_id": "GATEWAY-STAGING-SMOKE-R01",
        "target_resource_id": "RES-TEST-ONLY",
        "capability": "container.instance.restart",
    }
    check(_send(base + "/v1/intents", body=intent)[0] == 401, "ANONYMOUS")
    check(_send(base + "/v1/intents", body=intent, token="invalid-key")[0] == 401, "INVALID_TOKEN")

    code, receipt = _send(base + "/v1/intents", body=intent, token=key)
    check(code == 200, "RECEIPT_STATUS")
    check(receipt.get("result") == "DENY", "RECEIPT_DENY")
    check(receipt.get("reason_code") == "WARDEN_NOT_PROVISIONED", "RECEIPT_REASON")
    check(receipt.get("execution_invoked") is False, "NO_EXECUTION")
    check(bool(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("evidence_hash", "")))), "DIGEST")
    check(receipt.get("request_id") == intent["request_id"], "REQUEST_ID")

    code, replay = _send(base + "/v1/intents", body=intent, token=key)
    check(code == 200 and replay == receipt, "IDEMPOTENT_REPLAY")

    changed = {**intent, "capability": "different.scope"}
    check(_send(base + "/v1/intents", body=changed, token=key)[0] == 409, "REUSE_CONFLICT")

    print("STAGING_SMOKE_PASS: health, readiness, auth deny, receipt, replay and conflict")


if __name__ == "__main__":
    main()
