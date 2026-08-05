from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .errors import AuthorizationError
from .models import CapabilityGrant


class CapabilityVerifier(Protocol):
    def verify(
        self,
        *,
        capability_id: str,
        subject_id: str,
        resource_id: str,
        allowed_action: str,
        at: datetime,
    ) -> CapabilityGrant: ...


class InMemoryCapabilityVerifier:
    def __init__(self) -> None:
        self.capabilities: dict[str, CapabilityGrant] = {}

    def verify(
        self,
        *,
        capability_id: str,
        subject_id: str,
        resource_id: str,
        allowed_action: str,
        at: datetime,
    ) -> CapabilityGrant:
        capability = self.capabilities.get(capability_id)
        if (
            capability is None
            or capability.expires_at <= at
            or capability.subject_id != subject_id
            or capability.resource_id not in {resource_id, "*"}
            or capability.allowed_action not in {allowed_action, "CONTROL_TOWER_MANAGE", "*"}
        ):
            raise AuthorizationError(
                "Capability is missing, revoked, expired or does not match the requested operation",
                reason_codes=["CAPABILITY_INACTIVE"],
            )
        return capability
