from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import CapabilityAuthorization


class CapabilityVerifier(Protocol):
    def verify(
        self,
        *,
        capability_id: str,
        box_id: str,
        principal_id: str,
        context_id: str,
        resource_id: str,
        required_actions: set[str],
        purpose: str,
        at: datetime,
    ) -> CapabilityAuthorization | None: ...


class InMemoryCapabilityVerifier:
    def __init__(self) -> None:
        self.capabilities: dict[str, CapabilityAuthorization] = {}

    def verify(
        self,
        *,
        capability_id: str,
        box_id: str,
        principal_id: str,
        context_id: str,
        resource_id: str,
        required_actions: set[str],
        purpose: str,
        at: datetime,
    ) -> CapabilityAuthorization | None:
        capability = self.capabilities.get(capability_id)
        if capability is None or capability.expires_at <= at:
            return None
        if capability.box_id != box_id or capability.subject_id != principal_id:
            return None
        if capability.context_id != context_id or capability.purpose != purpose:
            return None
        if capability.allowed_action not in required_actions | {"RUNTIME_MANAGE", "*"}:
            return None
        if capability.resource_id not in {resource_id, box_id, "*"}:
            return None
        return capability
