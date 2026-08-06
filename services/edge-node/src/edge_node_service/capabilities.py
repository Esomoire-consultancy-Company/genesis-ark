from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    capability_id: str
    subject_id: str
    resource_id: str
    allowed_action: str
    expires_at: datetime


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
        self.grants: dict[str, CapabilityGrant] = {}
        self.revoked: set[str] = set()

    def add(self, grant: CapabilityGrant) -> None:
        self.grants[grant.capability_id] = grant

    def revoke(self, capability_id: str) -> None:
        self.revoked.add(capability_id)

    def verify(
        self,
        *,
        capability_id: str,
        subject_id: str,
        resource_id: str,
        allowed_action: str,
        at: datetime,
    ) -> CapabilityGrant:
        from .errors import AuthorizationError

        grant = self.grants.get(capability_id)
        if grant is None or capability_id in self.revoked:
            raise AuthorizationError(
                "Capability is missing or revoked",
                reason_codes=["CAPABILITY_INACTIVE"],
            )
        if grant.subject_id != subject_id:
            raise AuthorizationError(
                "Capability subject does not match",
                reason_codes=["CAPABILITY_SUBJECT_MISMATCH"],
            )
        if grant.resource_id != resource_id:
            raise AuthorizationError(
                "Capability resource does not match",
                reason_codes=["CAPABILITY_RESOURCE_MISMATCH"],
            )
        if grant.allowed_action != allowed_action:
            raise AuthorizationError(
                "Capability action does not match",
                reason_codes=["CAPABILITY_ACTION_MISMATCH"],
            )
        if grant.expires_at <= at:
            raise AuthorizationError(
                "Capability has expired",
                reason_codes=["CAPABILITY_EXPIRED"],
            )
        return grant
