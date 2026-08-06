from __future__ import annotations

import pytest

from control_tower_service.config import Settings


def test_postgres_backend_requires_database_url():
    with pytest.raises(ValueError, match="database_url"):
        Settings(repository_backend="postgres", database_url=None)


def test_command_ttl_configuration_is_bounded():
    with pytest.raises(ValueError, match="command TTLs"):
        Settings(default_command_ttl_seconds=4000, max_command_ttl_seconds=3600)


def test_missing_server_token_returns_configuration_error():
    from fastapi.testclient import TestClient

    from control_tower_service.app import create_app
    from control_tower_service.capabilities import InMemoryCapabilityVerifier
    from control_tower_service.repository import InMemoryControlTowerRepository

    app = create_app(
        settings=Settings(api_token=None),
        repository=InMemoryControlTowerRepository(),
        capability_verifier=InMemoryCapabilityVerifier(),
    )
    with TestClient(app) as client:
        response = client.get(
            "/v1/fleet/assets",
            headers={"X-Client-Cert-Verified": "SUCCESS"},
        )
    assert response.status_code == 503
    assert response.json()["reason_codes"] == ["AUTH_CONFIGURATION_MISSING"]
