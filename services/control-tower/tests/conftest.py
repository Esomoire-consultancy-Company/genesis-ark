from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from control_tower_service.app import create_app
from control_tower_service.capabilities import InMemoryCapabilityVerifier
from control_tower_service.config import Settings
from control_tower_service.models import CapabilityGrant, SourceFleetObservation
from control_tower_service.repository import InMemoryControlTowerRepository

NOW = datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def repository() -> InMemoryControlTowerRepository:
    repo = InMemoryControlTowerRepository()
    repo.seed_observation(
        SourceFleetObservation(
            node_id="NODE-001",
            node_class="EDGE",
            region="IN-KA",
            jurisdiction="IN",
            runtime_status="ACTIVE",
            edge_status="ACTIVE",
            last_seen_at=NOW - timedelta(seconds=10),
            capacity={"cpu_millis": 4000, "memory_mb": 8192},
            active_instances=2,
            active_sessions=3,
            pending_commands=0,
            latest_metrics={"cpu_percent": 12.5},
        )
    )
    return repo


@pytest.fixture
def verifier() -> InMemoryCapabilityVerifier:
    verifier = InMemoryCapabilityVerifier()
    verifier.capabilities["CAP-START"] = CapabilityGrant(
        capability_id="CAP-START",
        subject_id="ACTOR-OPS",
        resource_id="NODE-001",
        allowed_action="EDGE_START_INSTANCE",
        expires_at=NOW + timedelta(hours=1),
    )
    verifier.capabilities["CAP-RECOVER"] = CapabilityGrant(
        capability_id="CAP-RECOVER",
        subject_id="ACTOR-OPS",
        resource_id="NODE-001",
        allowed_action="RUNTIME_RECOVERY_EXECUTE",
        expires_at=NOW + timedelta(hours=1),
    )
    return verifier


@pytest.fixture
def app(repository, verifier):
    app = create_app(
        Settings(api_token="test-token", degraded_after_seconds=90, offline_after_seconds=300),
        repository=repository,
        capability_verifier=verifier,
    )
    app.state.engine.clock = lambda: NOW
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "x-client-cert-verified": "SUCCESS",
    }
