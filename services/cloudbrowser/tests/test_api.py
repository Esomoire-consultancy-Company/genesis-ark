from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import AUTH_HEADERS, SUBJECT_ID, create_session


def test_authentication_requires_mtls_and_bearer(client: TestClient) -> None:
    response = client.post("/v1/browser-sessions", json={})
    assert response.status_code == 401
    assert "MTLS_NOT_VERIFIED" in response.json()["reason_codes"]


def test_create_navigate_approve_and_terminate_flow(client: TestClient) -> None:
    session = create_session(client)
    session_id = session["browser_session_id"]
    assert session["session_status"] == "ACTIVE"

    navigation = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-NAVIGATE-0001",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://example.com/dashboard",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
            "estimated_network_bytes": 5000,
        },
    )
    assert navigation.status_code == 200, navigation.text
    assert navigation.json()["decision"] == "EXECUTED"

    submission = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-SUBMIT-0001",
            "action_type": "BROWSER_SUBMIT_FORM",
            "target_url": "https://example.com/orders",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["FORM_DATA"],
            "payload": {"form_reference": "FORM-ORDER-0001"},
            "estimated_network_bytes": 2000,
        },
    )
    assert submission.status_code == 200, submission.text
    assert submission.json()["decision"] == "APPROVAL_REQUIRED"

    approved = client.post(
        f"/v1/browser-sessions/{session_id}/approve",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-SUBMIT-0001",
            "approved_by": SUBJECT_ID,
            "approval_reason": "Order details verified",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["decision"] == "EXECUTED"
    assert "HUMAN_APPROVAL_GRANTED" in approved.json()["reason_codes"]

    usage = client.get(
        f"/v1/browser-sessions/{session_id}/usage",
        headers=AUTH_HEADERS,
    )
    assert usage.status_code == 200
    assert usage.json()["action_count"] == 2
    assert usage.json()["approval_count"] == 1

    terminated = client.post(
        f"/v1/browser-sessions/{session_id}/terminate",
        headers=AUTH_HEADERS,
        json={
            "terminated_by": SUBJECT_ID,
            "reason": "Actor completed the task",
        },
    )
    assert terminated.status_code == 200, terminated.text
    assert terminated.json()["session_status"] == "TERMINATED"


def test_openapi_exposes_canonical_cloudbrowser_operations(client: TestClient) -> None:
    generated = client.get("/openapi.json").json()
    operation_ids = {
        operation["operationId"]
        for path in generated["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operation_ids == {
        "createGovernedBrowserSession",
        "getGovernedBrowserSession",
        "evaluateGovernedBrowserAction",
        "approveGovernedBrowserAction",
        "pauseGovernedBrowserSession",
        "terminateGovernedBrowserSession",
        "getGovernedBrowserEvidence",
        "getGovernedBrowserUsage",
    }
    for path in generated["paths"].values():
        for method, operation in path.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation["security"] == [
                    {"mutualTLS": [], "bearerAuth": []}
                ]
