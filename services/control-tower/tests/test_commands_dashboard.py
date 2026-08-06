from __future__ import annotations

from datetime import timedelta

from control_tower_service.evidence import utcnow

from conftest import (
    APPROVER_ID,
    ASSET_ID,
    AUTH_HEADERS,
    DISPATCH_CAPABILITY_ID,
    ISSUER_ID,
    approval_request,
    asset_request,
    command_request,
    dispatch_request,
    incident_action,
    seed_asset,
    signal_request,
)

def test_low_impact_command_is_immediately_approved(client):
    seed_asset(client)
    response = client.post(
        "/v1/commands", headers=AUTH_HEADERS, json=command_request()
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "APPROVED"
    assert response.json()["high_impact"] is False

def test_high_impact_command_requires_independent_approval(client):
    seed_asset(client)
    created = client.post(
        "/v1/commands",
        headers=AUTH_HEADERS,
        json=command_request(command_type="DRAIN_NODE"),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "AUTHORIZATION_REQUIRED"
    rejected = client.post(
        "/v1/commands/COMMAND-FLEET-001/approve",
        headers=AUTH_HEADERS,
        json=approval_request(approver_id=ISSUER_ID),
    )
    assert rejected.status_code == 403
    assert "FOUR_EYES_REQUIRED" in rejected.json()["reason_codes"]

def test_approved_command_dispatches_edge_outbox_event(client):
    seed_asset(client)
    client.post(
        "/v1/commands",
        headers=AUTH_HEADERS,
        json=command_request(command_type="DRAIN_NODE"),
    )
    approved = client.post(
        "/v1/commands/COMMAND-FLEET-001/approve",
        headers=AUTH_HEADERS,
        json=approval_request(),
    )
    assert approved.status_code == 200, approved.text
    dispatched = client.post(
        "/v1/commands/COMMAND-FLEET-001/dispatch",
        headers=AUTH_HEADERS,
        json=dispatch_request(),
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "DISPATCHED"
    audit = client.get(f"/v1/audit/{ASSET_ID}", headers=AUTH_HEADERS).json()
    assert audit[-1]["event_type"] == "EDGE_COMMAND_REQUESTED"

def test_dispatch_rechecks_capability(client, verifier):
    seed_asset(client)
    client.post(
        "/v1/commands", headers=AUTH_HEADERS, json=command_request()
    )
    verifier.capabilities.pop(DISPATCH_CAPABILITY_ID)
    response = client.post(
        "/v1/commands/COMMAND-FLEET-001/dispatch",
        headers=AUTH_HEADERS,
        json=dispatch_request(),
    )
    assert response.status_code == 403

def test_command_idempotency_and_conflict(client):
    seed_asset(client)
    first = client.post("/v1/commands", headers=AUTH_HEADERS, json=command_request())
    repeated = client.post("/v1/commands", headers=AUTH_HEADERS, json=command_request())
    assert repeated.status_code == 201
    assert repeated.json()["issued_at"] == first.json()["issued_at"]
    conflict = client.post(
        "/v1/commands",
        headers=AUTH_HEADERS,
        json=command_request(parameters={"scope": "different"}),
    )
    assert conflict.status_code == 409

def test_command_completion_requires_dispatch(client):
    seed_asset(client)
    client.post("/v1/commands", headers=AUTH_HEADERS, json=command_request())
    premature = client.post(
        "/v1/commands/COMMAND-FLEET-001/complete",
        headers=AUTH_HEADERS,
        json={
            "status": "COMPLETED",
            "completed_by": "EDGE-AGENT-001",
            "result": {"ok": True},
        },
    )
    assert premature.status_code == 409
    client.post(
        "/v1/commands/COMMAND-FLEET-001/dispatch",
        headers=AUTH_HEADERS,
        json=dispatch_request(),
    )
    completed = client.post(
        "/v1/commands/COMMAND-FLEET-001/complete",
        headers=AUTH_HEADERS,
        json={
            "status": "COMPLETED",
            "completed_by": "EDGE-AGENT-001",
            "result": {"diagnostics": "healthy"},
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

def test_dashboard_aggregates_operational_state(client):
    seed_asset(client)
    client.post("/v1/signals", headers=AUTH_HEADERS, json=signal_request())
    client.post(
        "/v1/commands",
        headers=AUTH_HEADERS,
        json=command_request(command_type="DRAIN_NODE"),
    )
    dashboard = client.get("/v1/dashboard", headers=AUTH_HEADERS)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_assets"] == 1
    assert body["open_incidents"] == 1
    assert body["pending_authorizations"] == 1
    assert body["assets_by_status"]["HEALTHY"] == 1
