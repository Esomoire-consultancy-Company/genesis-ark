from __future__ import annotations

from typing import Any, Protocol

import httpx

from .config import Settings
from .errors import ForbiddenError, StateConflictError


class WardenClient(Protocol):
    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def issue(self, policy_decision_id: str, requested_by: str) -> dict[str, Any]: ...
    def revoke(
        self,
        capability_id: str,
        *,
        reason: str,
        revoked_by: str,
        policy_reference: str,
    ) -> dict[str, Any]: ...


class HttpWardenClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.warden_base_url.rstrip("/")
        self.api_token = settings.warden_api_token
        self.headers = {
            settings.trusted_mtls_header: settings.trusted_mtls_value,
        }
        if self.api_token is not None:
            self.headers["Authorization"] = f"Bearer {self.api_token}"

    def _request(self, method: str, path: str, json: dict[str, Any]) -> dict[str, Any]:
        if self.api_token is None:
            raise StateConflictError("CLOUDBROWSER_WARDEN_API_TOKEN is not configured")
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            headers=self.headers,
            json=json,
            timeout=10.0,
        )
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            if response.status_code == 403:
                raise ForbiddenError(detail)
            raise StateConflictError(detail)
        return response.json()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/policy-decisions/evaluate", payload)

    def issue(self, policy_decision_id: str, requested_by: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/capabilities/issue",
            {"policy_decision_id": policy_decision_id, "requested_by": requested_by},
        )

    def revoke(
        self,
        capability_id: str,
        *,
        reason: str,
        revoked_by: str,
        policy_reference: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/capabilities/{capability_id}/revoke",
            {
                "reason": reason,
                "revoked_by": revoked_by,
                "policy_reference": policy_reference,
            },
        )
