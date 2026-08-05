from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .errors import AuthenticationError

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


def build_auth_dependency(settings: Settings):
    async def authenticate(
        request: Request,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(bearer_scheme),
        ] = None,
    ) -> str:
        if settings.api_token is None:
            raise AuthenticationError(
                "WARDEN_API_TOKEN is not configured",
                reason_codes=["AUTH_CONFIGURATION_MISSING"],
            )
        mtls_value = request.headers.get(settings.trusted_mtls_header)
        if mtls_value != settings.trusted_mtls_value:
            raise AuthenticationError(
                "Trusted ingress did not confirm the client certificate",
                reason_codes=["MTLS_NOT_VERIFIED"],
            )
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not secrets.compare_digest(credentials.credentials, settings.api_token)
        ):
            raise AuthenticationError(
                "Bearer token is missing or invalid",
                reason_codes=["BEARER_INVALID"],
            )
        return "authenticated"

    return authenticate
