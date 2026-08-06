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

def test_authentication_requires_mtls_and_bearer(client):
    assert client.get("/v1/fleet/assets").status_code == 401
    assert client.get(
        "/v1/fleet/assets",
        headers={"Authorization": "Bearer test-token"},
    ).status_code == 401

def test_asset_upsert_and_read(client):
    created = seed_asset(client)
    assert created["asset_id"] == ASSET_ID
    fetched = client.get(f"/v1/fleet/assets/{ASSET_ID}", headers=AUTH_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["health_score"] == 100

def test_stale_asset_observation_is_rejected(client):
    created = seed_asset(client)
    stale = (utcnow() - timedelta(days=1)).isoformat()
    response = client.post(
        "/v1/fleet/assets",
        headers=AUTH_HEADERS,
        json=asset_request(observed_at=stale, health_score=10, status="DEGRADED"),
    )
    assert response.status_code == 409
    assert "STALE_FLEET_OBSERVATION" in response.json()["reason_codes"]
    assert created["health_score"] == 100

def test_signal_opens_and_correlates_incident(client):
    seed_asset(client)
    first = client.post("/v1/signals", headers=AUTH_HEADERS, json=signal_request())
    assert first.status_code == 202, first.text
    incident_id = first.json()["incident_id"]
    second_payload = signal_request(
        signal_id="SIGNAL-NODE-OFFLINE-002",
        severity="CRITICAL",
        summary="Node remains offline",
    )
    second = client.post(
        "/v1/signals",
        headers=AUTH_HEADERS,
        json=second_payload,
    )
    assert second.status_code == 202
    assert second.json()["incident_id"] == incident_id
    assert second.json()["occurrence_count"] == 2
    assert second.json()["severity"] == "CRITICAL"
    replay = client.post(
        "/v1/signals",
        headers=AUTH_HEADERS,
        json=second_payload,
    )
    assert replay.status_code == 202
    assert replay.json()["occurrence_count"] == 2

def test_signal_id_conflict_is_rejected(client):
    seed_asset(client)
    client.post("/v1/signals", headers=AUTH_HEADERS, json=signal_request())
    conflict = client.post(
        "/v1/signals",
        headers=AUTH_HEADERS,
        json=signal_request(summary="Different payload under same ID"),
    )
    assert conflict.status_code == 409
    assert "SIGNAL_ID_CONFLICT" in conflict.json()["reason_codes"]

def test_incident_acknowledgement_and_resolution(client):
    seed_asset(client)
    incident = client.post(
        "/v1/signals", headers=AUTH_HEADERS, json=signal_request()
    ).json()
    acknowledged = client.post(
        f"/v1/incidents/{incident['incident_id']}/acknowledge",
        headers=AUTH_HEADERS,
        json=incident_action("Investigating node reachability"),
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"
    resolved = client.post(
        f"/v1/incidents/{incident['incident_id']}/resolve",
        headers=AUTH_HEADERS,
        json=incident_action("Connectivity restored and attestation rechecked"),
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

def test_incident_action_denied_without_active_capability(client):
    seed_asset(client)
    incident = client.post(
        "/v1/signals", headers=AUTH_HEADERS, json=signal_request()
    ).json()
    response = client.post(
        f"/v1/incidents/{incident['incident_id']}/acknowledge",
        headers=AUTH_HEADERS,
        json=incident_action("Unauthorized", capability_id="CAP-MISSING-001"),
    )
    assert response.status_code == 403

def test_asset_audit_events_form_a_hash_chain(client):
    seed_asset(client)
    client.post(
        "/v1/fleet/assets",
        headers=AUTH_HEADERS,
        json=asset_request(
            status="DEGRADED",
            health_score=70,
            observed_at=(utcnow() + timedelta(seconds=1)).isoformat(),
        ),
    )
    events = client.get(f"/v1/audit/{ASSET_ID}", headers=AUTH_HEADERS).json()
    assert len(events) == 2
    assert events[0]["previous_event_hash"] is None
    assert events[1]["previous_event_hash"] == events[0]["evidence_hash"]

def test_openapi_requires_dual_authentication(client):
    schema = client.get("/openapi.json").json()
    assert {"bearerAuth", "mutualTLS"}.issubset(
        schema["components"]["securitySchemes"]
    )
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                assert operation["security"] == [
                    {"bearerAuth": [], "mutualTLS": []}
                ]
