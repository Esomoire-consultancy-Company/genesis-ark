from __future__ import annotations


class EdgeNodeError(Exception):
    status_code = 400
    title = "Edge Node Error"

    def __init__(self, detail: str, *, reason_codes: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_codes = reason_codes or ["EDGE_NODE_ERROR"]


class AuthenticationError(EdgeNodeError):
    status_code = 401
    title = "Authentication Failed"


class AuthorizationError(EdgeNodeError):
    status_code = 403
    title = "Authorization Failed"


class ConfigurationError(EdgeNodeError):
    status_code = 503
    title = "Service Configuration Error"


class NotFoundError(EdgeNodeError):
    status_code = 404
    title = "Not Found"


class StateConflictError(EdgeNodeError):
    status_code = 409
    title = "State Conflict"


class SignatureError(EdgeNodeError):
    status_code = 401
    title = "Node Signature Invalid"
