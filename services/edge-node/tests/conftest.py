from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from edge_node_service.app import create_app
from edge_node_service.capabilities import CapabilityGrant, InMemoryCapabilityVerifier
from edge_node_service.config import Settings
from edge_node_service.models import CommandType, EnrollNodeRequest
from edge_node_service.repository import InMemoryEdgeNodeRepository
from edge_node_service.signatures import StaticSecretResolver


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def repo(clock: MutableClock) -> InMemoryEdgeNodeRepository:
    value = InMemoryEdgeNodeRepository()
    value.seed_bootstrap_token(
        "node-001",
        "bootstrap-token-0000000000000001",
        clock.value + timedelta(hours=1),
    )
    return value


@pytest.fixture
def verifier(clock: MutableClock) -> InMemoryCapabilityVerifier:
    value = InMemoryCapabilityVerifier()
    action_map = {
        CommandType.START_INSTANCE: "EDGE_START_INSTANCE",
        CommandType.STOP_INSTANCE: "EDGE_STOP_INSTANCE",
        CommandType.PAUSE_SESSION: "EDGE_PAUSE_SESSION",
        CommandType.TERMINATE_SESSION: "EDGE_TERMINATE_SESSION",
        CommandType.EXECUTE_RECOVERY: "RUNTIME_RECOVERY_EXECUTE",
        CommandType.ROTATE_AGENT: "EDGE_ROTATE_AGENT",
        CommandType.DRAIN_NODE: "EDGE_DRAIN_NODE",
    }
    for index, action in enumerate(action_map.values(), start=1):
        value.add(
            CapabilityGrant(
                capability_id=f"cap-{index:03d}",
                subject_id="operator-001",
                resource_id="node-001",
                allowed_action=action,
                expires_at=clock.value + timedelta(hours=1),
            )
        )
    return value


@pytest.fixture
def secret_resolver() -> StaticSecretResolver:
    return StaticSecretResolver({"vault:edge/node-001": b"edge-node-secret"})


@pytest.fixture
def app(repo, verifier, secret_resolver, clock):
    value = create_app(
        Settings(api_token="test-token"),
        repository=repo,
        capability_verifier=verifier,
        secret_resolver=secret_resolver,
    )
    value.state.engine.clock = clock
    return value


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "x-client-cert-verified": "SUCCESS",
    }


@pytest.fixture
def enrollment_request() -> EnrollNodeRequest:
    return EnrollNodeRequest(
        node_id="node-001",
        device_id="device-001",
        agent_id="edge-agent-001",
        hardware_fingerprint="a" * 64,
        agent_version="1.0.0",
        bootstrap_token="bootstrap-token-0000000000000001",
        credential_reference="vault:edge/node-001",
        attestation_reference="attestation-001",
    )


@pytest.fixture
def enrolled_engine(app, enrollment_request):
    app.state.engine.enroll(enrollment_request)
    return app.state.engine
