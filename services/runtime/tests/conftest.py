from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from runtime_service.app import create_app
from runtime_service.capabilities import InMemoryCapabilityVerifier
from runtime_service.config import Settings
from runtime_service.evidence import utcnow
from runtime_service.models import CapabilityAuthorization
from runtime_service.repository import InMemoryRuntimeRepository

AUTH_HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Client-Cert-Verified": "SUCCESS",
}

NODE_ID = "NODE-BLR-001"
INSTANCE_ID = "RUNTIME-INSTANCE-001"
BOX_ID = "BOX-PERSONAL-001"
SUBJECT_ID = "DIGITALME-FAIZ-001"
CONTEXT_ID = "CONTEXT-PERSONAL-001"
SESSION_CAPABILITY_ID = "CAP-RUNTIME-SESSION-001"
RESOURCE_CAPABILITY_ID = "CAP-RUNTIME-RESOURCE-001"
SESSION_ID = "RUNTIME-SESSION-001"
PURPOSE = "operate personal Actor Box runtime"


@pytest.fixture
def repository() -> InMemoryRuntimeRepository:
    return InMemoryRuntimeRepository()


@pytest.fixture
def verifier() -> InMemoryCapabilityVerifier:
    result = InMemoryCapabilityVerifier()
    expires_at = utcnow() + timedelta(hours=1)
    result.capabilities[SESSION_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=SESSION_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=SUBJECT_ID,
        context_id=CONTEXT_ID,
        resource_id=INSTANCE_ID,
        allowed_action="RUNTIME_SESSION_START",
        purpose=PURPOSE,
        expires_at=expires_at,
    )
    result.capabilities[RESOURCE_CAPABILITY_ID] = CapabilityAuthorization(
        capability_id=RESOURCE_CAPABILITY_ID,
        box_id=BOX_ID,
        subject_id=SUBJECT_ID,
        context_id=CONTEXT_ID,
        resource_id=SESSION_ID,
        allowed_action="RUNTIME_RESOURCE_ALLOCATE",
        purpose=PURPOSE,
        expires_at=expires_at,
    )
    return result


@pytest.fixture
def client(
    repository: InMemoryRuntimeRepository,
    verifier: InMemoryCapabilityVerifier,
) -> TestClient:
    app = create_app(
        repository=repository,
        capability_verifier=verifier,
        settings=Settings(api_token="test-token"),
    )
    with TestClient(app) as test_client:
        yield test_client


def node_request(**overrides):
    payload = {
        "node_id": NODE_ID,
        "node_class": "REGIONAL_COMPUTE",
        "region": "IN-KA-BLR",
        "jurisdiction": "IN-KA",
        "authority_reference": "AUTH-GENESIS-RUNTIME-001",
        "attestation_reference": "ATTEST-NODE-001",
        "capacity": {
            "cpu_millis": 8000,
            "memory_mb": 16384,
            "gpu_millis": 2000,
            "storage_mb": 100000,
            "network_egress_mb": 50000,
            "browser_slots": 8,
        },
    }
    payload.update(overrides)
    return payload


def instance_request(**overrides):
    payload = {
        "instance_id": INSTANCE_ID,
        "node_id": NODE_ID,
        "box_id": BOX_ID,
        "runtime_class": "ACTOR_BOX",
        "runtime_version": "1.0.0",
        "requested_by": SUBJECT_ID,
        "authority_reference": "AUTH-GENESIS-RUNTIME-001",
        "resource_limits": {
            "cpu_millis": 2000,
            "memory_mb": 4096,
            "gpu_millis": 0,
            "storage_mb": 10000,
            "network_egress_mb": 5000,
            "browser_slots": 2,
        },
    }
    payload.update(overrides)
    return payload


def session_request(**overrides):
    payload = {
        "session_id": SESSION_ID,
        "instance_id": INSTANCE_ID,
        "box_id": BOX_ID,
        "principal_id": SUBJECT_ID,
        "context_id": CONTEXT_ID,
        "capability_id": SESSION_CAPABILITY_ID,
        "session_type": "ACTOR",
        "purpose": PURPOSE,
        "requested_duration_seconds": 1200,
    }
    payload.update(overrides)
    return payload


def seed_active_instance(client: TestClient) -> None:
    assert client.post(
        "/v1/runtime-nodes", headers=AUTH_HEADERS, json=node_request()
    ).status_code == 201
    assert client.post(
        "/v1/runtime-instances", headers=AUTH_HEADERS, json=instance_request()
    ).status_code == 201
    attested = client.post(
        f"/v1/runtime-instances/{INSTANCE_ID}/attest",
        headers=AUTH_HEADERS,
        json={
            "integrity_status": "ATTESTED",
            "attestation_reference": "ATTEST-INSTANCE-001",
            "attested_by": "GENESIS-ATTESTOR-001",
        },
    )
    assert attested.status_code == 200, attested.text
