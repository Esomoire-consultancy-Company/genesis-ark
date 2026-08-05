from __future__ import annotations


class WardenError(Exception):
    status_code = 400
    title = "Warden request failed"
    type_uri = "urn:vsr:warden:error"

    def __init__(self, detail: str, *, reason_codes: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_codes = reason_codes or []


class NotFoundError(WardenError):
    status_code = 404
    title = "Control object not found"
    type_uri = "urn:vsr:warden:not-found"


class StateConflictError(WardenError):
    status_code = 409
    title = "Authoritative state conflict"
    type_uri = "urn:vsr:warden:state-conflict"


class ForbiddenError(WardenError):
    status_code = 403
    title = "Authority denied"
    type_uri = "urn:vsr:warden:forbidden"


class AuthenticationError(WardenError):
    status_code = 401
    title = "Caller authentication failed"
    type_uri = "urn:vsr:warden:unauthenticated"
