from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import (
    AUTH_HEADERS,
    BOX_ID,
    SUBJECT_ID,
    decision_request,
)


def test_authentication_requires_mtls_and_bearer(client: TestClient) -> None:
    response = client.post(
        "/v1/policy-decisions/evaluate",
        json=decision_request(),
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "MTLS_NOT_VERIFIED" in response.json()["reason_codes"]


def test_evaluate_issue_revoke_and_lock_flow(client: TestClient) -> None:
    evaluated = client.post(
        "/v1/policy-decisions/evaluate",
        headers=AUTH_HEADERS,
        json=decision_request(),
    )
    assert evaluated.status_code == 200, evaluated.text
    decision = evaluated.json()
    assert decision["outcome"] == "RESTRICT"

    issued = client.post(
        "/v1/capabilities/issue",
        headers=AUTH_HEADERS,
        json={
            "policy_decision_id": decision["policy_decision_id"],
            "requested_by": SUBJECT_ID,
        },
    )
    assert issued.status_code == 201, issued.text
    capability = issued.json()
    assert capability["capability_status"] == "ISSUED"

    control = client.get(
        f"/v1/boxes/{BOX_ID}/control-state",
        headers=AUTH_HEADERS,
    )
    assert control.status_code == 200, control.text
    assert control.json()["active_capability_count"] == 1

    revoked = client.post(
        f"/v1/capabilities/{capability['capability_id']}/revoke",
        headers=AUTH_HEADERS,
        json={
            "reason": "Actor withdrew authority",
            "revoked_by": SUBJECT_ID,
            "policy_reference": "WARDEN-REVOCATION-POLICY-V1",
        },
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["target_type"] == "CAPABILITY"

    locked = client.post(
        f"/v1/boxes/{BOX_ID}/lock",
        headers=AUTH_HEADERS,
        json={
            "reason": "Device reported lost",
            "initiated_by": SUBJECT_ID,
            "policy_reference": "WARDEN-EMERGENCY-LOCK-V1",
        },
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["locked"] is True
    assert locked.json()["status"] == "SUSPENDED"
    assert locked.json()["active_capability_count"] == 0

    denied_after_lock = client.post(
        "/v1/policy-decisions/evaluate",
        headers=AUTH_HEADERS,
        json=decision_request(),
    )
    assert denied_after_lock.status_code == 200
    assert denied_after_lock.json()["outcome"] == "DENY"
    assert "BOX_NOT_EXECUTABLE" in denied_after_lock.json()["reason_codes"]


def test_openapi_operation_ids_match_canonical_contract(
    client: TestClient,
) -> None:
    generated = client.get("/openapi.json").json()
    operation_ids = {
        operation["operationId"]
        for path in generated["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert operation_ids == {
        "evaluateActorBoxPolicy",
        "issueActorBoxCapability",
        "revokeActorBoxCapability",
        "lockActorBox",
        "getActorBoxControlState",
    }
    assert generated["components"]["securitySchemes"]["mutualTLS"] == {
        "type": "mutualTLS"
    }
    for path in generated["paths"].values():
        for method, operation in path.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation["security"] == [
                    {"mutualTLS": [], "bearerAuth": []}
                ]


def test_evidence_events_form_a_hash_chain(client: TestClient) -> None:
    evaluated = client.post(
        "/v1/policy-decisions/evaluate",
        headers=AUTH_HEADERS,
        json=decision_request(),
    )
    assert evaluated.status_code == 200
    decision = evaluated.json()

    issued = client.post(
        "/v1/capabilities/issue",
        headers=AUTH_HEADERS,
        json={
            "policy_decision_id": decision["policy_decision_id"],
            "requested_by": SUBJECT_ID,
        },
    )
    assert issued.status_code == 201

    events = client.app.state.registry.evidence
    assert len(events) == 2
    assert events[0].previous_event_hash is None
    assert events[1].previous_event_hash == events[0].evidence_hash
    assert events[1].evidence_hash != events[0].evidence_hash
