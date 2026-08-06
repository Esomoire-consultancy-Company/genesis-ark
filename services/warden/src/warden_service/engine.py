from __future__ import annotations

from datetime import timedelta

from .config import Settings
from .errors import ForbiddenError, NotFoundError, StateConflictError
from .evidence import build_evidence_event, new_id, utcnow
from .models import (
    BoxControlState,
    BoxLockRequest,
    BoxStatus,
    CapabilityGrant,
    CapabilityIssueRequest,
    CapabilityStatus,
    ControlStatus,
    DecisionOutcome,
    DecisionRecord,
    PolicyDecision,
    PolicyDecisionRequest,
    Revocation,
    RevocationRequest,
    RuntimeIntegrity,
)
from .repository import RegistryRepository

EXECUTABLE_BOX_STATES = {BoxStatus.ACTIVE, BoxStatus.RESTRICTED}
WRITE_MARKERS = ("WRITE", "UPDATE", "DELETE", "CREATE", "APPROVE", "SETTLE", "TRANSFER", "RECONCILE")


class WardenEngine:
    def __init__(self, registry: RegistryRepository, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings

    def evaluate(self, request: PolicyDecisionRequest) -> PolicyDecision:
        now = utcnow()
        reasons: list[str] = []
        outcome = DecisionOutcome.DENY
        required_approval: str | None = None
        allowed_action = request.requested_action
        constraints: dict[str, object] = {
            "external_transmission": False,
            "non_transferable": True,
        }

        box = self.registry.get_box(request.box_id)
        if box is None:
            return self._record_decision(request, outcome, ["BOX_NOT_FOUND"], now)
        if box.locked or box.status not in EXECUTABLE_BOX_STATES:
            return self._record_decision(
                request,
                outcome,
                ["BOX_NOT_EXECUTABLE", f"BOX_STATUS_{box.status}"],
                now,
            )
        reasons.append("BOX_EXECUTABLE")

        runtime = self.registry.get_runtime(request.runtime_id)
        if runtime is None or runtime.box_id != request.box_id:
            return self._record_decision(request, outcome, [*reasons, "RUNTIME_NOT_BOUND"], now)
        if runtime.integrity_status != RuntimeIntegrity.ATTESTED:
            return self._record_decision(
                request,
                outcome,
                [*reasons, f"RUNTIME_{runtime.integrity_status}"],
                now,
            )
        reasons.append("RUNTIME_ATTESTED")

        binding = self.registry.find_binding(request.box_id, request.subject_id, now)
        if binding is None:
            return self._record_decision(
                request, outcome, [*reasons, "DIGITALME_BINDING_INACTIVE"], now
            )
        reasons.append("DIGITALME_BINDING_ACTIVE")

        context = self.registry.get_context(request.context_id)
        if (
            context is None
            or context.box_id != request.box_id
            or context.status != ControlStatus.ACTIVE
            or context.principal_id != request.subject_id
            or context.activated_at > now
            or (context.expires_at is not None and now >= context.expires_at)
        ):
            return self._record_decision(request, outcome, [*reasons, "CONTEXT_INACTIVE"], now)
        reasons.append("CONTEXT_ACTIVE")

        profile = self.registry.get_policy_profile(box.policy_profile_id)
        if (
            profile is None
            or profile.box_id != request.box_id
            or profile.status != ControlStatus.ACTIVE
            or profile.effective_from > now
            or (profile.effective_until is not None and now >= profile.effective_until)
        ):
            return self._record_decision(request, outcome, [*reasons, "POLICY_PROFILE_INACTIVE"], now)
        reasons.append("POLICY_PROFILE_ACTIVE")

        consent = self.registry.find_consent(request.box_id, request.subject_id, now)
        if consent is None:
            return self._record_decision(request, outcome, [*reasons, "CONSENT_NOT_FOUND"], now)
        if consent.purpose != request.purpose:
            return self._record_decision(request, outcome, [*reasons, "CONSENT_PURPOSE_MISMATCH"], now)
        if request.requested_action not in consent.action_scope:
            return self._record_decision(request, outcome, [*reasons, "CONSENT_ACTION_OUT_OF_SCOPE"], now)
        if not set(request.data_classes).issubset(set(consent.data_scope)):
            return self._record_decision(request, outcome, [*reasons, "CONSENT_DATA_OUT_OF_SCOPE"], now)
        reasons.append("CONSENT_ACTIVE")

        if request.source_zone and request.destination_zone and request.source_zone != request.destination_zone:
            rules = self.registry.boundary_rules(request.box_id, now)
            missing_data_classes = [
                data_class
                for data_class in request.data_classes
                if not any(
                    rule.source_zone == request.source_zone
                    and rule.destination_zone == request.destination_zone
                    and rule.data_class == data_class
                    and rule.permitted_purpose == request.purpose
                    for rule in rules
                )
            ]
            if missing_data_classes:
                return self._record_decision(
                    request,
                    outcome,
                    [*reasons, "DATA_BOUNDARY_DENIED", *[f"DATA_CLASS_{value}" for value in missing_data_classes]],
                    now,
                )
            reasons.append("DATA_BOUNDARY_ALLOWED")

        if request.agent_id:
            delegation = self.registry.find_delegation(request.box_id, request.agent_id, now)
            if delegation is None or delegation.delegating_principal_id != request.subject_id:
                return self._record_decision(request, outcome, [*reasons, "DELEGATION_INACTIVE"], now)
            if request.requested_action not in delegation.permitted_actions:
                return self._record_decision(request, outcome, [*reasons, "DELEGATION_ACTION_OUT_OF_SCOPE"], now)
            if not set(request.data_classes).issubset(set(delegation.permitted_data_scope)):
                return self._record_decision(request, outcome, [*reasons, "DELEGATION_DATA_OUT_OF_SCOPE"], now)
            if context.workspace_id not in delegation.workspace_scope:
                return self._record_decision(request, outcome, [*reasons, "DELEGATION_WORKSPACE_OUT_OF_SCOPE"], now)
            reasons.append("DELEGATION_ACTIVE")

            write_potential = any(marker in request.requested_action.upper() for marker in WRITE_MARKERS)
            if delegation.write_requires_human_approval and write_potential and not request.human_approval_present:
                outcome = DecisionOutcome.RESTRICT
                allowed_action = "READ_ONLY"
                required_approval = "HUMAN_APPROVAL_FOR_WRITE"
                constraints["write_requires_human_approval"] = True
                reasons.append("WRITE_REQUIRES_HUMAN_APPROVAL")

        ttl = min(
            request.requested_duration_seconds,
            profile.max_capability_ttl_seconds,
            self.settings.max_capability_ttl_seconds,
        )
        if ttl < request.requested_duration_seconds:
            constraints["requested_duration_seconds"] = request.requested_duration_seconds
            constraints["effective_duration_seconds"] = ttl
            reasons.append("DURATION_RESTRICTED")
            if outcome != DecisionOutcome.RESTRICT:
                outcome = DecisionOutcome.RESTRICT

        if outcome == DecisionOutcome.DENY:
            outcome = DecisionOutcome.ALLOW
            reasons.append("POLICY_SATISFIED")

        capability = CapabilityGrant(
            capability_id=new_id("CAP"),
            box_id=request.box_id,
            subject_id=request.agent_id or request.subject_id,
            resource_id=request.resource_id,
            allowed_action=allowed_action,
            purpose=request.purpose,
            context_id=request.context_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl),
            policy_decision_id="DECISION-PENDING",
            capability_status=CapabilityStatus.ISSUED,
            constraints=constraints,
        )
        return self._record_decision(
            request,
            outcome,
            reasons,
            now,
            capability=capability,
            required_approval=required_approval,
            policy_bundle_version=profile.policy_bundle_version,
        )

    def issue_capability(self, request: CapabilityIssueRequest) -> CapabilityGrant:
        now = utcnow()
        record = self.registry.get_decision(request.policy_decision_id)
        if record is None:
            raise NotFoundError(f"Policy decision {request.policy_decision_id} does not exist")
        decision = record.decision
        if decision.outcome not in {DecisionOutcome.ALLOW, DecisionOutcome.RESTRICT}:
            raise ForbiddenError(
                "Policy decision does not authorize capability issuance",
                reason_codes=[f"DECISION_{decision.outcome}"],
            )
        if decision.capability is None:
            raise StateConflictError("Policy decision has no capability grant")
        if request.requested_by != record.request.subject_id:
            raise ForbiddenError(
                "Only the bound DigitalMe principal may materialize this capability",
                reason_codes=["REQUESTER_NOT_PRINCIPAL"],
            )
        box = self.registry.get_box(record.request.box_id)
        if box is None or box.locked or box.status not in EXECUTABLE_BOX_STATES:
            raise StateConflictError("Actor Box is no longer executable")
        if now >= decision.capability.expires_at:
            raise StateConflictError("Capability grant has expired before issuance")

        existing = self.registry.get_capability(decision.capability.capability_id)
        if existing is not None:
            return existing

        event = self._build_event(
            box_id=decision.capability.box_id,
            event_type="CAPABILITY_ISSUED",
            actor_id=record.request.subject_id,
            agent_id=record.request.agent_id,
            context_id=decision.capability.context_id,
            action_reference=decision.capability.capability_id,
            policy_decision=decision.outcome,
            payload=decision.capability.model_dump(mode="json"),
        )
        return self.registry.issue_capability(decision.capability, event)

    def revoke_capability(self, capability_id: str, request: RevocationRequest) -> Revocation:
        capability = self.registry.get_capability(capability_id)
        if capability is None:
            raise NotFoundError(f"Capability {capability_id} does not exist")
        now = utcnow()
        event = self._build_event(
            box_id=capability.box_id,
            event_type="CAPABILITY_REVOKED",
            actor_id=request.revoked_by,
            context_id=capability.context_id,
            action_reference=capability_id,
            policy_decision="REVOKE",
            payload=request.model_dump(mode="json"),
        )
        revocation = Revocation(
            revocation_id=new_id("REVOKE"),
            box_id=capability.box_id,
            target_type="CAPABILITY",
            target_id=capability_id,
            reason=request.reason,
            revoked_by=request.revoked_by,
            effective_at=now,
            policy_reference=request.policy_reference,
            evidence_event_id=event.event_id,
        )
        self.registry.revoke_capability(capability_id, revocation, event)
        return revocation

    def lock_box(self, box_id: str, request: BoxLockRequest) -> BoxControlState:
        now = utcnow()
        box = self.registry.get_box(box_id)
        if box is None:
            raise NotFoundError(f"Actor Box {box_id} does not exist")
        event = self._build_event(
            box_id=box_id,
            event_type="BOX_LOCKED",
            actor_id=request.initiated_by,
            action_reference=box_id,
            policy_decision="EMERGENCY_LOCK",
            payload=request.model_dump(mode="json"),
        )
        self.registry.lock_box(box_id, now, request.reason, event)
        return self.control_state(box_id)

    def control_state(self, box_id: str) -> BoxControlState:
        now = utcnow()
        box = self.registry.get_box(box_id)
        if box is None:
            raise NotFoundError(f"Actor Box {box_id} does not exist")
        runtime = self.registry.get_runtime_for_box(box_id)
        context = self.registry.get_active_context(box_id, now)
        if runtime is None or context is None:
            raise StateConflictError("Box control state is incomplete")
        latest = self.registry.latest_evidence(box_id)
        if latest is None:
            latest = self._emit(
                box_id=box_id,
                event_type="CONTROL_STATE_READ",
                actor_id=context.principal_id,
                context_id=context.context_id,
                action_reference=box_id,
                policy_decision="READ",
                payload={"bootstrap": True},
            )
        return BoxControlState(
            box_id=box_id,
            status=box.status,
            runtime_integrity=runtime.integrity_status,
            active_context_id=context.context_id,
            active_capability_count=len(self.registry.active_capabilities(box_id, now)),
            active_agent_count=self.registry.active_agent_count(box_id, now),
            locked=box.locked,
            updated_at=box.updated_at,
            evidence_event_id=latest.event_id,
        )

    def _record_decision(
        self,
        request: PolicyDecisionRequest,
        outcome: DecisionOutcome,
        reasons: list[str],
        now,
        *,
        capability: CapabilityGrant | None = None,
        required_approval: str | None = None,
        policy_bundle_version: str | None = None,
    ) -> PolicyDecision:
        decision_id = new_id("DECISION")
        if capability is not None:
            capability = capability.model_copy(update={"policy_decision_id": decision_id})
        evidence = self._build_event(
            box_id=request.box_id,
            event_type="POLICY_DECISION",
            actor_id=request.subject_id,
            agent_id=request.agent_id,
            context_id=request.context_id,
            action_reference=request.request_id,
            policy_decision=outcome,
            payload={"reason_codes": reasons, "requested_action": request.requested_action},
            allow_missing_box=True,
        )
        decision = PolicyDecision(
            policy_decision_id=decision_id,
            request_id=request.request_id,
            decided_at=now,
            outcome=outcome,
            reason_codes=reasons,
            policy_bundle_version=policy_bundle_version or self.settings.policy_bundle_version,
            capability=capability,
            required_approval=required_approval,
            evidence_event_id=evidence.event_id,
        )
        self.registry.record_decision(
            DecisionRecord(decision=decision, request=request), evidence
        )
        return decision

    def _build_event(
        self,
        *,
        box_id: str,
        event_type: str,
        actor_id: str,
        action_reference: str,
        policy_decision: str,
        payload: dict,
        agent_id: str | None = None,
        context_id: str | None = None,
        allow_missing_box: bool = False,
    ):
        latest = self.registry.latest_evidence(box_id)
        if not allow_missing_box and self.registry.get_box(box_id) is None:
            raise NotFoundError(f"Actor Box {box_id} does not exist")
        return build_evidence_event(
            box_id=box_id,
            event_type=event_type,
            actor_id=actor_id,
            agent_id=agent_id,
            context_id=context_id,
            action_reference=action_reference,
            policy_decision=str(policy_decision),
            payload=payload,
            previous_event_hash=latest.evidence_hash if latest else None,
        )

    def _emit(self, **kwargs):
        event = self._build_event(**kwargs)
        self.registry.append_evidence(event)
        return event
