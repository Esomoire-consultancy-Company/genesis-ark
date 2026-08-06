from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from control_tower_service.app import create_app
from control_tower_service.capabilities import InMemoryCapabilityVerifier
from control_tower_service.config import Settings
from control_tower_service.evidence import utcnow
from control_tower_service.models import CapabilityAuthorization
from control_tower_service.repository import InMemoryControlTowerRepository

AUTH_HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Client-Cert-Verified": "SUCCESS",
}

ASSET_ID = "NODE-BLR-001"
ANCHOR_ID = "ANCHOR-GENESIS-001"
BOX_ID = "BOX-OPS-001"
CONTEXT_ID = "CONTEXT-CONTROL-TOWER-001"
ISSUER_ID = "DIGITALME-OPERATOR-001"
APPROVER_ID = "DIGITALME-APPROVER-001"
DISPATCHER_ID = "DIGITALME-DISPATCHER-001"
ISSUE_CAPABILITY_ID = "CAP-CONTROL-ISSUE-001"
APPROVE_CAPABILITY_ID = "CAP-CONTROL-APPROVE-001"
DISPATCH_CAPABILITY_ID = "CAP-CONTROL-DISPATCH-001"
INCIDENT_CAPABILITY_ID = "CAP-CONTROL-INCIDENT-001"
ISSUE_PURPOSE = "operate governed fleet"
APPROVE_PURPOSE = "approve high impact fleet command"
DISPATCH_PURPOSE = "dispatch approved fleet command"
INCIDENT_PURPOSE = "manage fleet incident"


@pytest.fixture
def repository() -> InMemoryControlTowerRepository:
    return InMemoryControlTowerRepository()


@pytest.fixture
def verifier() -> InMemoryCapabilityVerifier:
    result = InMemoryCapabilityVerifier()
    expires = utcnow() + timedelta(hours=1)
    result.capabilities[ISSUE_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=ISSUE_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=ISSUER_ID,
        context_id=CONTEXT_ID,
        resource_id=ASSET_ID,
        allowed_action="CONTROL_TOWER_COMMAND_ISSUE",
        purpose=ISSUE_PURPOSE,
        expires_at=expires,
    )
    result.capabilities[APPROVE_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=APPROVE_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=APPROVER_ID,
        context_id=CONTEXT_ID,
        resource_id="*",
        allowed_action="CONTROL_TOWER_COMMAND_APPROVE",
        purpose=APPROVE_PURPOSE,
        expires_at=expires,
    )
    result.capabilities[DISPATCH_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=DISPATCH_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=DISPATCHER_ID,
        context_id=CONTEXT_ID,
        resource_id="*",
        allowed_action="CONTROL_TOWER_COMMAND_DISPATCH",
        purpose=DISPATCH_PURPOSE,
        expires_at=expires,
    )
    result.capabilities[INCIDENT_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=INCIDENT_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=ISSUER_ID,
        context_id=CONTEXT_ID,
        resource_id="*",
        allowed_action="CONTROL_TOWER_MANAGE",
        purpose=INCIDENT_PURPOSE,
        expires_at=expires,
    )
    return result


@pytest.fixture
def client(
    repository: InMemoryControlTowerRepository,
    verifier: InMemoryCapabilityVerifier,
) -> TestClient:
    app = create_app(
        repository=repository,
        capability_verifier=verifier,
        settings=Settings(api_token="test-token"),
    )
    with TestClient(app) as test_client:
        yield test_client


def asset_request(**overrides):
    payload = {
        "asset_id": ASSET_ID,
        "asset_type": "RUNTIME_NODE",
        "anchor_id": ANCHOR_ID,
        "authority_reference": "AUTH-GENESIS-RUNTIME-001",
        "owner_reference": "GENESIS-OPERATIONS-001",
        "region": "IN-KA-BLR",
        "jurisdiction": "IN-KA",
        "status": "HEALTHY",
        "health_score": 100,
        "attestation_reference": "ATTEST-NODE-001",
        "policy_version": "warden-policy-1.0.0",
        "observed_at": utcnow().isoformat(),
        "metadata": {"runtime_version": "1.0.0"},
    }
    payload.update(overrides)
    return payload


def seed_asset(client: TestClient, **overrides) -> dict:
    response = client.post(
        "/v1/fleet/assets",
        headers=AUTH_HEADERS,
        json=asset_request(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def signal_request(**overrides):
    payload = {
        "signal_id": "SIGNAL-NODE-OFFLINE-001",
        "subject_asset_id": ASSET_ID,
        "signal_type": "NODE_OFFLINE",
        "severity": "HIGH",
        "summary": "Edge node stopped reporting heartbeats",
        "source_reference": "EDGE-MONITOR-001",
        "observed_at": utcnow().isoformat(),
        "details": {"missed_heartbeats": 3},
    }
    payload.update(overrides)
    return payload


def incident_action(note: str, **overrides):
    payload = {
        "actor_id": ISSUER_ID,
        "box_id": BOX_ID,
        "context_id": CONTEXT_ID,
        "capability_id": INCIDENT_CAPABILITY_ID,
        "purpose": INCIDENT_PURPOSE,
        "note": note,
    }
    payload.update(overrides)
    return payload


def command_request(command_type: str = "RUN_DIAGNOSTICS", **overrides):
    payload = {
        "command_id": "COMMAND-FLEET-001",
        "target_asset_id": ASSET_ID,
        "command_type": command_type,
        "issuer_id": ISSUER_ID,
        "box_id": BOX_ID,
        "context_id": CONTEXT_ID,
        "capability_id": ISSUE_CAPABILITY_ID,
        "purpose": ISSUE_PURPOSE,
        "parameters": {"scope": "runtime"},
        "requested_ttl_seconds": 900,
    }
    payload.update(overrides)
    return payload


def approval_request(**overrides):
    payload = {
        "approver_id": APPROVER_ID,
        "box_id": BOX_ID,
        "context_id": CONTEXT_ID,
        "approval_capability_id": APPROVE_CAPABILITY_ID,
        "purpose": APPROVE_PURPOSE,
        "reason": "Independent operational approval",
    }
    payload.update(overrides)
    return payload


def dispatch_request(**overrides):
    payload = {
        "actor_id": DISPATCHER_ID,
        "box_id": BOX_ID,
        "context_id": CONTEXT_ID,
        "capability_id": DISPATCH_CAPABILITY_ID,
        "purpose": DISPATCH_PURPOSE,
    }
    payload.update(overrides)
    return payload
