"""Staging-only private-network acceptance check.

Executes a bounded set of HTTP requests against the deny-only gateway.
No public domain, Docker adapter or database administrator credentials needed.
"""
from __future__ import annotations

import json
import os
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
    opener = request.build_opener(request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=8) as resp:
            return resp.status, json.load(resp)
    except error.HTTPError as exc:
        return exc.code, json.load(exc)


def main():
    base = os.environ.get("GENESIS_GATEWAY_INTERNAL_URL", "").rstrip("/")
    key = os.environ.get("GENESIS_GATEWAY_API_KEY", "")
    addr = parse.urlparse(base)
    if addr.scheme != "http" or not (addr.hostname or "").endswith(".railway.internal"):
        raise SystemExit("SMOKE_TARGET_NOT_PRIVATE")
    if len(key) < 32:
        raise SystemExit("SMOKE_API_KEY_MISSING")

    assert _send(base + "/healthz")[0] == 200
    code, ready = _send(base + "/readyz")
    assert code == 200 and ready.get("execution_enabled") is False
    assert ready.get("mode") == "deny-only"

    intent = {
        "request_id": str(uuid4()),
        "correlation_id": "GATEWAY-STAGING-SMOKE-R01",
        "target_resource_id": "RES-TEST-ONLY",
        "capability": "container.instance.restart",
    }
    assert _send(base + "/v1/intents", body=intent)[0] == 401
    assert _send(base + "/v1/intents", body=intent, token="invalid-key")[0] == 401

    code, receipt = _send(base + "/v1/intents", body=intent, token=key)
    assert code == 200
    assert receipt["result"] == "DENY"
    assert receipt["reason_code"] == "WARDEN_NOT_PROVISIONED"
    assert receipt["execution_invoked"] is False
    assert len(receipt["evidence_hash"]) == 64
    assert receipt["request_id"] == intent["request_id"]

    code, replay = _send(base + "/v1/intents", body=intent, token=key)
    assert code == 200 and replay == receipt

    changed = {**intent, "capability": "different.scope"}
    assert _send(base + "/v1/intents", body=changed, token=key)[0] == 409

    print("STAGING_SMOKE_PASS: health, readiness, auth deny, receipt, replay and conflict")


if __name__ == "__main__":
    main()
