from __future__ import annotations

import asyncio

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from runtime_service.auth import build_auth_dependency
from runtime_service.config import Settings
from runtime_service.errors import AuthenticationError


def test_non_ascii_bearer_is_rejected_without_encoding_error() -> None:
    authenticate = build_auth_dependency(Settings(api_token="test-token"))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-client-cert-verified", b"SUCCESS")],
        }
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="🔒",
    )
    with pytest.raises(AuthenticationError) as exc_info:
        asyncio.run(authenticate(request, credentials))
    assert exc_info.value.reason_codes == ["BEARER_INVALID"]
