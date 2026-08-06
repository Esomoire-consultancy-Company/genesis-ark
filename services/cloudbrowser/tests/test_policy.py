from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import AUTH_HEADERS, SUBJECT_ID, create_session


def test_disallowed_domain_is_denied(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    response = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-DOMAIN-DENY-0001",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://unapproved.example.net",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert "DOMAIN_NOT_ALLOWED" in response.json()["reason_codes"]


def test_raw_secret_payload_is_rejected(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    response = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-SECRET-0001",
            "action_type": "BROWSER_USE_CREDENTIAL",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["CREDENTIAL_REFERENCE"],
            "payload": {
                "credential_reference": "VAULT-CREDENTIAL-0001",
                "password": "must-not-enter-browser-payload",
            },
        },
    )
    assert response.status_code == 403
    assert "RAW_SECRET_REJECTED" in response.json()["reason_codes"]


def test_credential_reference_executes_without_raw_secret(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    response = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-CREDENTIAL-0001",
            "action_type": "BROWSER_USE_CREDENTIAL",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["CREDENTIAL_REFERENCE"],
            "payload": {"credential_reference": "VAULT-CREDENTIAL-0001"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "EXECUTED"


def test_upload_is_denied_when_policy_disables_uploads(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    response = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-UPLOAD-0001",
            "action_type": "BROWSER_UPLOAD_FILE",
            "target_url": "https://example.com/upload",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["FORM_DATA"],
            "payload": {"file_reference": "QUARANTINE-FILE-0001"},
            "estimated_file_bytes": 1000,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert "UPLOAD_DISABLED" in response.json()["reason_codes"]


def test_only_bound_digitalme_can_approve(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    pending = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-APPROVAL-0001",
            "action_type": "BROWSER_SUBMIT_FORM",
            "target_url": "https://example.com/orders",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["FORM_DATA"],
        },
    )
    assert pending.json()["decision"] == "APPROVAL_REQUIRED"
    response = client.post(
        f"/v1/browser-sessions/{session_id}/approve",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-APPROVAL-0001",
            "approved_by": "DIGITALME-OTHER-0001",
            "approval_reason": "Attempted external approval",
        },
    )
    assert response.status_code == 403
    assert "APPROVER_NOT_PRINCIPAL" in response.json()["reason_codes"]


def test_pause_blocks_new_actions(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    paused = client.post(
        f"/v1/browser-sessions/{session_id}/pause",
        headers=AUTH_HEADERS,
        json={"paused_by": SUBJECT_ID, "reason": "Actor requested review"},
    )
    assert paused.status_code == 200
    assert paused.json()["session_status"] == "PAUSED"
    action = client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-AFTER-PAUSE-0001",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://example.com",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
        },
    )
    assert action.status_code == 409


def test_evidence_is_hash_chained(client: TestClient) -> None:
    session_id = create_session(client)["browser_session_id"]
    client.post(
        f"/v1/browser-sessions/{session_id}/actions/evaluate",
        headers=AUTH_HEADERS,
        json={
            "action_id": "BROWSER-ACTION-EVIDENCE-0001",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://example.com",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
        },
    )
    response = client.get(
        f"/v1/browser-sessions/{session_id}/evidence",
        headers=AUTH_HEADERS,
    )
    events = response.json()
    assert len(events) == 3
    assert events[0]["previous_event_hash"] is None
    assert events[1]["event_type"] == "BROWSER_ACTION_AUTHORIZED"
    assert events[1]["previous_event_hash"] == events[0]["evidence_hash"]
    assert events[2]["event_type"] == "BROWSER_ACTION_EXECUTED"
    assert events[2]["previous_event_hash"] == events[1]["evidence_hash"]
