from __future__ import annotations

from datetime import timedelta

from control_tower_service.models import PublicationSourceEvent, SourceFleetObservation

from conftest import NOW


def refresh(client, headers):
    return client.post("/v1/control-tower/fleet/refresh", headers=headers, json={"actor_id": "ACTOR-OPS"})


def command_payload(command_type="START_INSTANCE"):
    return {
        "request_id": f"REQUEST-{command_type}",
        "node_id": "NODE-001",
        "command_type": command_type,
        "requested_by": "ACTOR-REQUESTER",
        "target_reference": "INSTANCE-001",
        "payload": {},
        "purpose": "Operate the governed runtime",
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
    }


def test_auth_requires_mtls_and_bearer(client):
    assert client.get("/v1/control-tower/dashboard").status_code == 401
    assert client.get("/v1/control-tower/dashboard", headers={"Authorization": "Bearer test-token"}).status_code == 401


def test_refresh_builds_online_fleet_snapshot(client, headers):
    response = refresh(client, headers)
    assert response.status_code == 200
    assert response.json()["refreshed_node_ids"] == ["NODE-001"]
    node = client.get("/v1/control-tower/nodes/NODE-001", headers=headers).json()
    assert node["effective_status"] == "ONLINE"
    assert node["active_instances"] == 2
    assert node["heartbeat_age_seconds"] == 10


def test_offline_refresh_opens_and_online_refresh_resolves_system_incident(client, headers, repository):
    repository.seed_observation(SourceFleetObservation(node_id="NODE-001", node_class="EDGE", region="IN-KA", jurisdiction="IN", runtime_status="ACTIVE", edge_status="ACTIVE", last_seen_at=NOW - timedelta(minutes=10)))
    first = refresh(client, headers).json()
    assert len(first["opened_incident_ids"]) == 1
    incidents = client.get("/v1/control-tower/incidents", headers=headers).json()
    assert incidents[0]["incident_type"] == "NODE_OFFLINE"
    assert incidents[0]["status"] == "OPEN"
    repository.seed_observation(SourceFleetObservation(node_id="NODE-001", node_class="EDGE", region="IN-KA", jurisdiction="IN", runtime_status="ACTIVE", edge_status="ACTIVE", last_seen_at=NOW - timedelta(seconds=5)))
    second = refresh(client, headers).json()
    assert second["resolved_incident_ids"] == first["opened_incident_ids"]


def test_command_authorization_and_dispatch_rechecks_capability(client, headers, repository):
    refresh(client, headers)
    created = client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload())
    assert created.status_code == 201
    assert created.json()["status"] == "AUTHORIZATION_REQUIRED"
    authorized = client.post("/v1/control-tower/command-requests/REQUEST-START_INSTANCE/authorize", headers=headers, json={"decision": "APPROVE", "actor_id": "ACTOR-OPS", "reason": "Approved maintenance operation", "capability_id": "CAP-START"})
    assert authorized.status_code == 200
    assert authorized.json()["status"] == "AUTHORIZED"
    dispatched = client.post("/v1/control-tower/command-requests/REQUEST-START_INSTANCE/dispatch", headers=headers, json={"actor_id": "ACTOR-OPS"})
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "DISPATCHED"
    command_id = dispatched.json()["dispatched_command_id"]
    assert repository.dispatched_commands[command_id].required_capability_action == "EDGE_START_INSTANCE"


def test_revoked_capability_blocks_dispatch(client, headers, verifier):
    refresh(client, headers)
    client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload())
    client.post("/v1/control-tower/command-requests/REQUEST-START_INSTANCE/authorize", headers=headers, json={"decision": "APPROVE", "actor_id": "ACTOR-OPS", "reason": "ok", "capability_id": "CAP-START"})
    del verifier.capabilities["CAP-START"]
    response = client.post("/v1/control-tower/command-requests/REQUEST-START_INSTANCE/dispatch", headers=headers, json={"actor_id": "ACTOR-OPS"})
    assert response.status_code == 403
    assert response.json()["reason_codes"] == ["CAPABILITY_INACTIVE"]


def test_command_can_be_rejected_without_capability(client, headers):
    refresh(client, headers)
    client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload())
    response = client.post("/v1/control-tower/command-requests/REQUEST-START_INSTANCE/authorize", headers=headers, json={"decision": "REJECT", "actor_id": "ACTOR-OPS", "reason": "Unsafe timing"})
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"


def test_quarantined_node_only_accepts_recovery_class_commands(client, headers, repository):
    repository.seed_observation(SourceFleetObservation(node_id="NODE-001", node_class="EDGE", region="IN-KA", jurisdiction="IN", runtime_status="QUARANTINED", edge_status="QUARANTINED", last_seen_at=NOW))
    refresh(client, headers)
    blocked = client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload())
    assert blocked.status_code == 409
    allowed = client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload("EXECUTE_RECOVERY"))
    assert allowed.status_code == 201


def test_manual_incident_lifecycle(client, headers):
    refresh(client, headers)
    created = client.post("/v1/control-tower/incidents", headers=headers, json={"incident_id": "INCIDENT-MANUAL-001", "node_id": "NODE-001", "severity": "WARNING", "incident_type": "CAPACITY_PRESSURE", "summary": "Memory pressure requires investigation", "opened_by": "ACTOR-OPS", "evidence_references": ["EVIDENCE-001"]})
    assert created.status_code == 201
    for status in ["ACKNOWLEDGED", "MITIGATING", "RESOLVED", "CLOSED"]:
        response = client.post("/v1/control-tower/incidents/INCIDENT-MANUAL-001/transition", headers=headers, json={"status": status, "actor_id": "ACTOR-OPS", "note": f"Move to {status}"})
        assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def test_invalid_incident_transition_is_rejected(client, headers):
    refresh(client, headers)
    client.post("/v1/control-tower/incidents", headers=headers, json={"incident_id": "INCIDENT-MANUAL-002", "node_id": "NODE-001", "severity": "INFO", "incident_type": "TEST", "summary": "Test incident", "opened_by": "ACTOR-OPS"})
    response = client.post("/v1/control-tower/incidents/INCIDENT-MANUAL-002/transition", headers=headers, json={"status": "CLOSED", "actor_id": "ACTOR-OPS", "note": "Skip states"})
    assert response.status_code == 409


def test_publication_lease_and_acknowledgement_are_exact_and_idempotent(client, headers, repository):
    repository.seed_outbox_event(PublicationSourceEvent(stream="RUNTIME", event_id="RUNTIME-EVENT-001", aggregate_id="INSTANCE-001", event_type="RUNTIME_INSTANCE_ACTIVE", evidence_hash="a" * 64, payload={"instance_id": "INSTANCE-001"}, occurred_at=NOW - timedelta(minutes=1)))
    lease = client.post("/v1/control-tower/publications/lease", headers=headers, json={"publisher_id": "RIVER-PUBLISHER", "max_events": 1, "lease_seconds": 60}).json()
    assert lease["events"][0]["event_id"] == "RUNTIME-EVENT-001"
    ack = client.post(f"/v1/control-tower/publications/{lease['lease_id']}/ack", headers=headers, json={"publisher_id": "RIVER-PUBLISHER", "lease_token": lease["lease_token"], "items": [{"stream": "RUNTIME", "event_id": "RUNTIME-EVENT-001", "destination_reference": "RIVER-RECEIPT-001"}]})
    assert ack.status_code == 200
    assert ack.json()["acknowledged_event_ids"] == ["RUNTIME-EVENT-001"]


def test_publication_ack_must_match_the_complete_lease(client, headers, repository):
    for suffix in ["001", "002"]:
        repository.seed_outbox_event(PublicationSourceEvent(stream="EDGE", event_id=f"EDGE-EVENT-{suffix}", aggregate_id="NODE-001", event_type="EDGE_EVENT", evidence_hash=("b" if suffix == "001" else "c") * 64, payload={}, occurred_at=NOW))
    lease = client.post("/v1/control-tower/publications/lease", headers=headers, json={"publisher_id": "RIVER-PUBLISHER", "max_events": 2}).json()
    response = client.post(f"/v1/control-tower/publications/{lease['lease_id']}/ack", headers=headers, json={"publisher_id": "RIVER-PUBLISHER", "lease_token": lease["lease_token"], "items": [{"stream": lease["events"][0]["stream"], "event_id": lease["events"][0]["event_id"], "destination_reference": "RIVER-ONLY-ONE"}]})
    assert response.status_code == 409
    assert response.json()["reason_codes"] == ["PUBLICATION_ACK_SET_MISMATCH"]


def test_dashboard_aggregates_operational_state(client, headers):
    refresh(client, headers)
    client.post("/v1/control-tower/command-requests", headers=headers, json=command_payload())
    body = client.get("/v1/control-tower/dashboard", headers=headers).json()
    assert body["total_nodes"] == 1
    assert body["nodes_by_status"]["ONLINE"] == 1
    assert body["authorization_queue"] == 1
    assert body["unpublished_evidence"] >= 1
