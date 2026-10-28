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
    res = client.post("/v1/intents", json=intent(), headers={"Authorization": "Bearer caf\u00e9"})
    assert res.status_code == 401
