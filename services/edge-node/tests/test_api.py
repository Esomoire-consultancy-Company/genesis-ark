from __future__ import annotations

from datetime import timedelta

from edge_node_service.models import (
    CommandType,
    EdgeNodeStatus,
    HeartbeatRequest,
)
from edge_node_service.signatures import sign_heartbeat


def test_enrollment_is_one_time(client, auth_headers, enrollment_request):
    response = client.post(
        "/v1/edge-nodes/enroll",
        headers=auth_headers,
        json=enrollment_request.model_dump(mode="json"),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ENROLLED"

    duplicate = client.post(
        "/v1/edge-nodes/enroll",
        headers=auth_headers,
        json=enrollment_request.model_dump(mode="json"),
    )
    assert duplicate.status_code == 409
    assert "EDGE_NODE_ALREADY_ENROLLED" in duplicate.json()["reason_codes"]


def test_valid_heartbeat_activates_node_and_replay_is_rejected(
    client,
    auth_headers,
    enrolled_engine,
    secret_resolver,
    clock,
):
    provisional = HeartbeatRequest(
        sequence=1,
        sent_at=clock.value,
        agent_version="1.0.1",
        attestation_reference="attestation-001",
        runtime_digest="b" * 64,
        node_state=EdgeNodeStatus.ACTIVE,
        metrics={"cpu_percent": 12.5},
        signature="0" * 64,
    )
    request = provisional.model_copy(
        update={
            "signature": sign_heartbeat(
                secret_resolver.resolve("vault:edge/node-001"),
                "node-001",
                provisional,
            )
        }
    )
    response = client.post(
        "/v1/edge-nodes/node-001/heartbeats",
        headers=auth_headers,
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 202
    assert response.json()["node_status"] == "ACTIVE"

    replay = client.post(
        "/v1/edge-nodes/node-001/heartbeats",
        headers=auth_headers,
        json=request.model_dump(mode="json"),
    )
    assert replay.status_code == 409
    assert "HEARTBEAT_REPLAYED" in replay.json()["reason_codes"]


def test_invalid_heartbeat_signature_is_rejected(client, auth_headers, enrolled_engine, clock):
    request = HeartbeatRequest(
        sequence=1,
        sent_at=clock.value,
        agent_version="1.0.0",
        attestation_reference="attestation-001",
        runtime_digest="c" * 64,
        node_state=EdgeNodeStatus.ACTIVE,
        metrics={},
        signature="f" * 64,
    )
    response = client.post(
        "/v1/edge-nodes/node-001/heartbeats",
        headers=auth_headers,
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 401
    assert "HEARTBEAT_SIGNATURE_INVALID" in response.json()["reason_codes"]


def test_issue_lease_and_complete_command(client, auth_headers, enrolled_engine, clock):
    issue = client.post(
        "/v1/edge-nodes/node-001/commands",
        headers=auth_headers,
        json={
            "command_id": "command-001",
            "command_type": CommandType.START_INSTANCE.value,
            "capability_id": "cap-001",
            "issued_by": "operator-001",
            "target_reference": "runtime-001",
            "payload": {},
            "expires_at": (clock.value + timedelta(minutes=10)).isoformat(),
        },
    )
    assert issue.status_code == 201
    assert issue.json()["status"] == "PENDING"

    lease = client.post(
        "/v1/edge-nodes/node-001/commands/lease",
        headers=auth_headers,
        json={"agent_id": "edge-agent-001", "lease_seconds": 60},
    )
    assert lease.status_code == 200
    body = lease.json()
    assert body["command"]["status"] == "LEASED"

    complete = client.post(
        "/v1/edge-nodes/node-001/commands/command-001/complete",
        headers=auth_headers,
        json={
            "agent_id": "edge-agent-001",
            "lease_token": body["lease_token"],
            "status": "SUCCEEDED",
            "result": {"state": "RUNNING"},
        },
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "SUCCEEDED"


def test_wrong_agent_cannot_lease_command(client, auth_headers, enrolled_engine, clock):
    client.post(
        "/v1/edge-nodes/node-001/commands",
        headers=auth_headers,
        json={
            "command_id": "command-002",
            "command_type": "STOP_INSTANCE",
            "capability_id": "cap-002",
            "issued_by": "operator-001",
            "target_reference": "runtime-001",
            "payload": {},
            "expires_at": (clock.value + timedelta(minutes=10)).isoformat(),
        },
    )
    response = client.post(
        "/v1/edge-nodes/node-001/commands/lease",
        headers=auth_headers,
        json={"agent_id": "edge-agent-other", "lease_seconds": 60},
    )
    assert response.status_code == 403
    assert "EDGE_AGENT_ID_MISMATCH" in response.json()["reason_codes"]


def test_missing_authentication_is_rejected(client):
    response = client.get("/v1/edge-nodes/node-001")
    assert response.status_code == 401


def test_expired_lease_can_be_released_to_same_enrolled_agent(
    client,
    auth_headers,
    enrolled_engine,
    clock,
):
    client.post(
        "/v1/edge-nodes/node-001/commands",
        headers=auth_headers,
        json={
            "command_id": "command-lease-expiry",
            "command_type": "START_INSTANCE",
            "capability_id": "cap-001",
            "issued_by": "operator-001",
            "target_reference": "runtime-002",
            "payload": {},
            "expires_at": (clock.value + timedelta(minutes=10)).isoformat(),
        },
    )
    first = client.post(
        "/v1/edge-nodes/node-001/commands/lease",
        headers=auth_headers,
        json={"agent_id": "edge-agent-001", "lease_seconds": 1},
    ).json()
    clock.advance(seconds=2)
    second = client.post(
        "/v1/edge-nodes/node-001/commands/lease",
        headers=auth_headers,
        json={"agent_id": "edge-agent-001", "lease_seconds": 60},
    ).json()
    assert second["command"]["command_id"] == "command-lease-expiry"
    assert second["command"]["attempts"] == 2
    assert second["lease_token"] != first["lease_token"]


def test_stale_heartbeat_is_rejected(
    client,
    auth_headers,
    enrolled_engine,
    secret_resolver,
    clock,
):
    provisional = HeartbeatRequest(
        sequence=1,
        sent_at=clock.value - timedelta(minutes=10),
        agent_version="1.0.0",
        attestation_reference="attestation-001",
        runtime_digest="d" * 64,
        node_state=EdgeNodeStatus.ACTIVE,
        metrics={},
        signature="0" * 64,
    )
    request = provisional.model_copy(
        update={
            "signature": sign_heartbeat(
                secret_resolver.resolve("vault:edge/node-001"),
                "node-001",
                provisional,
            )
        }
    )
    response = client.post(
        "/v1/edge-nodes/node-001/heartbeats",
        headers=auth_headers,
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 409
    assert "HEARTBEAT_STALE" in response.json()["reason_codes"]
