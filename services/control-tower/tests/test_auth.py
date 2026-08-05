from __future__ import annotations

import asyncio
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from starlette.requests import Request

from control_tower_service.app import create_app
from control_tower_service.auth import build_auth_dependency
from control_tower_service.config import Settings
from control_tower_service.errors import AuthenticationError


def test_missing_api_token_fails_closed():
    client = TestClient(create_app(Settings(api_token=None)))
    response = client.get(
        "/v1/control-tower/dashboard",
        headers={"Authorization": "Bearer anything", "x-client-cert-verified": "SUCCESS"},
    )
    assert response.status_code == 503
    assert response.json()["reason_codes"] == ["AUTH_CONFIGURATION_MISSING"]


def test_non_ascii_bearer_cannot_crash_authentication():
    authenticate = build_auth_dependency(Settings(api_token="expected"))
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-client-cert-verified", b"SUCCESS")],
    })
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="café")
    with pytest.raises(AuthenticationError) as exc_info:
        asyncio.run(authenticate(request, credentials))
    assert exc_info.value.reason_codes == ["BEARER_INVALID"]
