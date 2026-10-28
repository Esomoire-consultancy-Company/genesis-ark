from uuid import uuid4

from fastapi.testclient import TestClient

from genesis_gateway.app import Settings, create_app
from genesis_gateway.ledger import IntentConflict

KEY = "a" * 40  # Test-only key; never use this value in a deployment.
CFG = Settings(api_key=KEY, issuer_id="DIGITALME-ACTOR-CI", database_url="postgresql://ci-invalid")


def intent(request_id=None):
    return {
        "request_id": str(request_id or uuid4()),
        "correlation_id": "COR-01",
        "target_resource_id": "RES-01",
        "capability": "container.instance.restart",
    }


class FakeLedger:
    def __init__(self, ready=True, broken=False):
        self.entries = {}
        self.is_ready = ready
        self.broken = broken

    def ready(self):
        if self.broken:
            raise OSError("Unavailable")
        return self.is_ready

    def record_denial(self, entry, issuer):
        if self.broken:
            raise OSError("Unavailable")
        key = entry["request_id"]
        previous = self.entries.get(key)
        if previous is not None:
            if previous["entry"] != entry or previous["issuer"] != issuer:
                raise IntentConflict()
            return previous["receipt"]
        receipt = {
            "request_id": key, "event_id": str(uuid4()), "result": "DENY",
            "reason_code": "WARDEN_NOT_PROVISIONED", "evidence_hash": "b" * 64,
            "previous_hash": None, "execution_invoked": False,
        }
        self.entries[key] = {"entry": entry, "issuer": issuer, "receipt": receipt}
        return receipt


def test_healthz_is_not_a_readiness_claim():
    res = TestClient(create_app(Settings(), None)).get("/healthz")
    assert res.status_code == 200
    assert res.json()["execution_enabled"] is False
    assert TestClient(create_app(Settings(), None)).get("/readyz").status_code == 503


def test_healthy_evidence_database_allows_deny_only_readiness():
    client = TestClient(create_app(CFG, FakeLedger()))
    assert client.get("/readyz").json() == {"status": "ready", "mode": "deny-only", "execution_enabled": False}


def test_missing_or_invalid_credentials_fail_closed():
    client = TestClient(create_app(CFG, FakeLedger()))
    assert client.post("/v1/intents", json=intent()).status_code == 401
    assert client.post("/v1/intents", json=intent(), headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_intent_is_logged_denied_and_never_executes():
    ledger = FakeLedger()
    client = TestClient(create_app(CFG, ledger))
    res = client.post("/v1/intents", json=intent(), headers={"Authorization": f"Bearer {KEY}"})
    assert res.status_code == 200
    assert res.json()["result"] == "DENY"
    assert res.json()["execution_invoked"] is False
    assert len(ledger.entries) == 1


def test_no_evidence_no_receipt():
    client = TestClient(create_app(CFG, FakeLedger(broken=True)))
    res = client.post("/v1/intents", json=intent(), headers={"Authorization": f"Bearer {KEY}"})
    assert res.status_code == 503
    assert res.json()["detail"] == "EVIDENCE_UNAVAILABLE"
    assert client.get("/readyz").status_code == 503


def test_unknown_fields_rejected():
    body = intent()
    body["execute"] = True
    res = TestClient(create_app(CFG, FakeLedger())).post("/v1/intents", json=body, headers={"Authorization": f"Bearer {KEY}"})
    assert res.status_code == 422


def test_duplicate_request_id_is_idempotent_but_reuse_conflicts():
    client = TestClient(create_app(CFG, FakeLedger()))
    body = intent()
    auth = {"Authorization": f"Bearer {KEY}"}
    first = client.post("/v1/intents", json=body, headers=auth)
    again = client.post("/v1/intents", json=body, headers=auth)
    assert first.status_code == 200 and first.json() == again.json()
    body["capability"] = "different.scope"
    assert client.post("/v1/intents", json=body, headers=auth).status_code == 409


def test_unconfigured_gateway_never_accepts_intents():
    client = TestClient(create_app(Settings(), FakeLedger()))
    assert client.post("/v1/intents", json=intent(), headers={"Authorization": f"Bearer {KEY}"}).status_code == 503


def test_settings_repr_never_exposes_credentials():
    rendered = repr(CFG)
    assert KEY not in rendered
    assert CFG.database_url not in rendered


def test_non_ascii_bearer_fails_with_401_not_500():
    client = TestClient(create_app(CFG, FakeLedger()))
    res = client.post("/v1/intents", json=intent(), headers={b"authorization": b"Bearer caf\xe9"})
    assert res.status_code == 401



def test_untrusted_exception_text_never_leaks_credentials(caplog):
    class LeakingLedger(FakeLedger):
        def ready(self):
            raise RuntimeError(f"private {CFG.database_url} {KEY}")

        def record_denial(self, entry, issuer):
            raise RuntimeError(f"private {CFG.database_url} {KEY}")

    client = TestClient(create_app(CFG, LeakingLedger()))
    assert client.get("/readyz").status_code == 503
    assert client.post(
        "/v1/intents", json=intent(), headers={"Authorization": f"Bearer {KEY}"}
    ).status_code == 503
    assert CFG.database_url not in caplog.text
    assert KEY not in caplog.text
    assert "RuntimeError" in caplog.text



def test_authenticated_write_never_bypasses_failed_readiness():
    store = FakeLedger(ready=False)
    client = TestClient(create_app(CFG, store))
    response = client.post(
        "/v1/intents", json=intent(),
        headers={"Authorization": f"Bearer {KEY}"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "EVIDENCE_SCHEMA_NOT_READY"
    assert store.entries == {}


def test_readiness_failure_does_not_leak_exception_text(caplog):
    class Unsafe(Exception):
        pass

    class NotReadyLedger(FakeLedger):
        def ready(self):
            raise Unsafe(f"password={KEY}; dsn={CFG.database_url}")

    client = TestClient(create_app(CFG, NotReadyLedger()))
    response = client.post(
        "/v1/intents", json=intent(),
        headers={"Authorization": f"Bearer {KEY}"}
    )
    assert response.status_code == 503
    assert KEY not in caplog.text
    assert CFG.database_url not in caplog.text


def test_rate_limit_and_full_spool_http_mappings():
    from genesis_gateway.ledger import CapacityExceeded

    class FullLedger(FakeLedger):
        def __init__(self, reason):
            super().__init__()
            self.reason = reason

        def record_denial(self, entry, issuer):
            raise CapacityExceeded(self.reason)

    auth = {"Authorization": f"Bearer {KEY}"}
    rate = TestClient(create_app(CFG, FullLedger("INTENT_RATE_LIMIT"))).post(
        "/v1/intents", json=intent(), headers=auth
    )
    assert rate.status_code == 429
    assert rate.json()["detail"] == "INTENT_RATE_LIMIT"
    assert rate.headers["retry-after"] == "60"

    full = TestClient(create_app(CFG, FullLedger("EVIDENCE_SPOOL_FULL"))).post(
        "/v1/intents", json=intent(), headers=auth
    )
    assert full.status_code == 503
    assert full.json()["detail"] == "EVIDENCE_SPOOL_FULL"
