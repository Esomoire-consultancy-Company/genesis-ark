from __future__ import annotations


class ControlTowerError(Exception):
    status_code = 400
    title = "Control Tower request failed"

    def __init__(self, detail: str, *, reason_codes: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_codes = reason_codes or ["CONTROL_TOWER_ERROR"]


class NotFoundError(ControlTowerError):
    status_code = 404
    title = "Control Tower object not found"


class StateConflictError(ControlTowerError):
    status_code = 409
    title = "Control Tower state conflict"


class AuthorizationError(ControlTowerError):
    status_code = 403
    title = "Control Tower authority denied"


class AuthenticationError(ControlTowerError):
    status_code = 401
    title = "Control Tower caller authentication failed"


class ConfigurationError(ControlTowerError):
    status_code = 503
    title = "Control Tower is not configured"
