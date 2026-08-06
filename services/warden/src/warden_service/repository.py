from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Protocol

from .errors import NotFoundError, StateConflictError
from .models import (
    ActorBoxRecord,
    BindingRecord,
    BoxStatus,
    BoundaryRuleRecord,
    CapabilityGrant,
    CapabilityStatus,
    ConsentRecord,
    ContextRecord,
    ControlStatus,
    DecisionRecord,
    DelegationRecord,
    EvidenceEvent,
    PolicyProfileRecord,
    Revocation,
    RuntimeRecord,
)


class RegistryRepository(Protocol):
    def get_box(self, box_id: str) -> ActorBoxRecord | None: ...
    def get_runtime(self, runtime_id: str) -> RuntimeRecord | None: ...
    def get_runtime_for_box(self, box_id: str) -> RuntimeRecord | None: ...
    def get_context(self, context_id: str) -> ContextRecord | None: ...
    def get_active_context(self, box_id: str, at: datetime) -> ContextRecord | None: ...
    def get_policy_profile(self, policy_profile_id: str) -> PolicyProfileRecord | None: ...
    def find_binding(self, box_id: str, digitalme_id: str, at: datetime) -> BindingRecord | None: ...
    def find_consent(self, box_id: str, digitalme_id: str, at: datetime) -> ConsentRecord | None: ...
    def find_delegation(self, box_id: str, agent_id: str, at: datetime) -> DelegationRecord | None: ...
    def boundary_rules(self, box_id: str, at: datetime) -> list[BoundaryRuleRecord]: ...
    def record_decision(self, record: DecisionRecord, event: EvidenceEvent) -> None: ...
    def get_decision(self, decision_id: str) -> DecisionRecord | None: ...
    def issue_capability(self, capability: CapabilityGrant, event: EvidenceEvent) -> CapabilityGrant: ...
    def get_capability(self, capability_id: str) -> CapabilityGrant | None: ...
    def revoke_capability(
        self,
        capability_id: str,
        revocation: Revocation,
        event: EvidenceEvent,
    ) -> None: ...
    def lock_box(
        self,
        box_id: str,
        at: datetime,
        reason: str,
        event: EvidenceEvent,
    ) -> None: ...
    def append_evidence(self, event: EvidenceEvent) -> None: ...
    def latest_evidence(self, box_id: str) -> EvidenceEvent | None: ...
    def active_capabilities(self, box_id: str, at: datetime) -> list[CapabilityGrant]: ...
    def active_agent_count(self, box_id: str, at: datetime) -> int: ...
    def close(self) -> None: ...


def _effective(status: ControlStatus, start: datetime, end: datetime | None, at: datetime) -> bool:
    return status == ControlStatus.ACTIVE and start <= at and (end is None or at < end)


class InMemoryRegistry:
    """Deterministic registry adapter for local execution and contract tests."""

    def __init__(self) -> None:
        self.boxes: dict[str, ActorBoxRecord] = {}
        self.runtimes: dict[str, RuntimeRecord] = {}
        self.bindings: dict[str, BindingRecord] = {}
        self.contexts: dict[str, ContextRecord] = {}
        self.policy_profiles: dict[str, PolicyProfileRecord] = {}
        self.consents: dict[str, ConsentRecord] = {}
        self.delegations: dict[str, DelegationRecord] = {}
        self.boundaries: dict[str, BoundaryRuleRecord] = {}
        self.decisions: dict[str, DecisionRecord] = {}
        self.capabilities: dict[str, CapabilityGrant] = {}
        self.revocations: dict[str, Revocation] = {}
        self.evidence: list[EvidenceEvent] = []
        self._lock = RLock()

    def get_box(self, box_id: str) -> ActorBoxRecord | None:
        return self.boxes.get(box_id)

    def get_runtime(self, runtime_id: str) -> RuntimeRecord | None:
        return self.runtimes.get(runtime_id)

    def get_runtime_for_box(self, box_id: str) -> RuntimeRecord | None:
        return next(
            (runtime for runtime in self.runtimes.values() if runtime.box_id == box_id),
            None,
        )

    def get_context(self, context_id: str) -> ContextRecord | None:
        return self.contexts.get(context_id)

    def get_active_context(self, box_id: str, at: datetime) -> ContextRecord | None:
        return next(
            (
                context
                for context in self.contexts.values()
                if context.box_id == box_id
                and _effective(context.status, context.activated_at, context.expires_at, at)
            ),
            None,
        )

    def get_policy_profile(self, policy_profile_id: str) -> PolicyProfileRecord | None:
        return self.policy_profiles.get(policy_profile_id)

    def find_binding(self, box_id: str, digitalme_id: str, at: datetime) -> BindingRecord | None:
        return next(
            (
                item
                for item in self.bindings.values()
                if item.box_id == box_id
                and item.digitalme_id == digitalme_id
                and _effective(item.status, item.effective_from, item.effective_until, at)
            ),
            None,
        )

    def find_consent(self, box_id: str, digitalme_id: str, at: datetime) -> ConsentRecord | None:
        return next(
            (
                item
                for item in self.consents.values()
                if item.box_id == box_id
                and item.digitalme_id == digitalme_id
                and _effective(item.status, item.effective_from, item.effective_until, at)
            ),
            None,
        )

    def find_delegation(self, box_id: str, agent_id: str, at: datetime) -> DelegationRecord | None:
        return next(
            (
                item
                for item in self.delegations.values()
                if item.box_id == box_id
                and item.agent_id == agent_id
                and _effective(item.status, item.effective_from, item.effective_until, at)
            ),
            None,
        )

    def boundary_rules(self, box_id: str, at: datetime) -> list[BoundaryRuleRecord]:
        return [
            item
            for item in self.boundaries.values()
            if item.box_id == box_id
            and _effective(item.status, item.effective_from, item.effective_until, at)
        ]

    def _append_evidence_locked(self, event: EvidenceEvent) -> None:
        latest = self.latest_evidence(event.box_id)
        expected = latest.evidence_hash if latest else None
        if event.previous_event_hash != expected:
            raise StateConflictError("Evidence event does not continue the Box hash chain")
        self.evidence.append(event)

    def record_decision(self, record: DecisionRecord, event: EvidenceEvent) -> None:
        with self._lock:
            if record.decision.policy_decision_id in self.decisions:
                raise StateConflictError("Policy decision ID already exists")
            if any(
                existing.request.request_id == record.request.request_id
                for existing in self.decisions.values()
            ):
                raise StateConflictError("Request ID has already been evaluated")
            self._append_evidence_locked(event)
            self.decisions[record.decision.policy_decision_id] = record

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        return self.decisions.get(decision_id)

    def issue_capability(self, capability: CapabilityGrant, event: EvidenceEvent) -> CapabilityGrant:
        with self._lock:
            existing = self.capabilities.get(capability.capability_id)
            if existing is not None:
                return existing
            self._append_evidence_locked(event)
            self.capabilities[capability.capability_id] = capability
            return capability

    def get_capability(self, capability_id: str) -> CapabilityGrant | None:
        return self.capabilities.get(capability_id)

    def revoke_capability(
        self,
        capability_id: str,
        revocation: Revocation,
        event: EvidenceEvent,
    ) -> None:
        with self._lock:
            capability = self.capabilities.get(capability_id)
            if capability is None:
                raise NotFoundError(f"Capability {capability_id} does not exist")
            if capability.capability_status == CapabilityStatus.REVOKED:
                raise StateConflictError("Capability is already revoked")
            self._append_evidence_locked(event)
            self.capabilities[capability_id] = capability.model_copy(
                update={"capability_status": CapabilityStatus.REVOKED}
            )
            self.revocations[revocation.revocation_id] = revocation

    def lock_box(
        self,
        box_id: str,
        at: datetime,
        reason: str,
        event: EvidenceEvent,
    ) -> None:
        with self._lock:
            box = self.boxes.get(box_id)
            if box is None:
                raise NotFoundError(f"Actor Box {box_id} does not exist")
            if box.locked:
                raise StateConflictError("Actor Box is already locked")
            self._append_evidence_locked(event)
            self.boxes[box_id] = box.model_copy(
                update={"locked": True, "status": BoxStatus.SUSPENDED, "updated_at": at}
            )
            for capability_id, capability in list(self.capabilities.items()):
                if (
                    capability.box_id == box_id
                    and capability.capability_status == CapabilityStatus.ISSUED
                ):
                    self.capabilities[capability_id] = capability.model_copy(
                        update={"capability_status": CapabilityStatus.SUSPENDED}
                    )

    def append_evidence(self, event: EvidenceEvent) -> None:
        with self._lock:
            self._append_evidence_locked(event)

    def latest_evidence(self, box_id: str) -> EvidenceEvent | None:
        return next((event for event in reversed(self.evidence) if event.box_id == box_id), None)

    def active_capabilities(self, box_id: str, at: datetime) -> list[CapabilityGrant]:
        return [
            capability
            for capability in self.capabilities.values()
            if capability.box_id == box_id
            and capability.capability_status == CapabilityStatus.ISSUED
            and capability.issued_at <= at < capability.expires_at
        ]

    def active_agent_count(self, box_id: str, at: datetime) -> int:
        return len(
            {
                delegation.agent_id
                for delegation in self.delegations.values()
                if delegation.box_id == box_id
                and _effective(
                    delegation.status,
                    delegation.effective_from,
                    delegation.effective_until,
                    at,
                )
            }
        )

    def close(self) -> None:
        return None
