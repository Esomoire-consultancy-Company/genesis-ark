from __future__ import annotations


class CloudBrowserError(Exception):
    status_code = 400
    title = "CloudBrowser request failed"
    type_uri = "urn:vsr:cloudbrowser:error"

    def __init__(self, detail: str, *, reason_codes: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_codes = reason_codes or []


class AuthenticationError(CloudBrowserError):
    status_code = 401
    title = "Caller authentication failed"
    type_uri = "urn:vsr:cloudbrowser:unauthenticated"


class ForbiddenError(CloudBrowserError):
    status_code = 403
    title = "Browser authority denied"
    type_uri = "urn:vsr:cloudbrowser:forbidden"


class NotFoundError(CloudBrowserError):
    status_code = 404
    title = "Browser control object not found"
    type_uri = "urn:vsr:cloudbrowser:not-found"


class StateConflictError(CloudBrowserError):
    status_code = 409
    title = "Browser session state conflict"
    type_uri = "urn:vsr:cloudbrowser:state-conflict"
