from __future__ import annotations


class RuntimeManagerError(Exception):
    status_code = 400
    title = "Runtime manager request failed"
    type_uri = "urn:vsr:runtime:error"

    def __init__(self, detail: str, *, reason_codes: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_codes = reason_codes or []


class NotFoundError(RuntimeManagerError):
    status_code = 404
    title = "Runtime object not found"
    type_uri = "urn:vsr:runtime:not-found"


class StateConflictError(RuntimeManagerError):
    status_code = 409
    title = "Runtime state conflict"
    type_uri = "urn:vsr:runtime:state-conflict"


class ForbiddenError(RuntimeManagerError):
    status_code = 403
    title = "Runtime authority denied"
    type_uri = "urn:vsr:runtime:forbidden"


class AuthenticationError(RuntimeManagerError):
    status_code = 401
    title = "Runtime caller authentication failed"
    type_uri = "urn:vsr:runtime:unauthenticated"


class ConfigurationError(RuntimeManagerError):
    status_code = 503
    title = "Runtime manager is not configured"
    type_uri = "urn:vsr:runtime:configuration-unavailable"
