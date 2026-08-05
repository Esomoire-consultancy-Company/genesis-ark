from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .errors import AuthenticationError, ConfigurationError

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


def build_auth_dependency(settings: Settings):
    async def authenticate(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
    ) -> str:
        if not settings.api_token:
            raise ConfigurationError(
                "CONTROL_TOWER_API_TOKEN is not configured",
                reason_codes=["AUTH_CONFIGURATION_MISSING"],
            )
        if request.headers.get(settings.trusted_mtls_header) != settings.trusted_mtls_value:
            raise AuthenticationError(
                "Trusted ingress did not confirm the client certificate",
                reason_codes=["MTLS_NOT_VERIFIED"],
            )
        supplied = credentials.credentials if credentials is not None else ""
        try:
            valid = (
                credentials is not None
                and credentials.scheme.lower() == "bearer"
                and secrets.compare_digest(supplied.encode("utf-8"), settings.api_token.encode("utf-8"))
            )
        except UnicodeEncodeError:
            valid = False
        if not valid:
            raise AuthenticationError(
                "Bearer token is missing or invalid",
                reason_codes=["BEARER_INVALID"],
            )
        return "authenticated"

    return authenticate
