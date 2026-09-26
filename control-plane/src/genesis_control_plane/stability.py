from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from genesis_control_plane.contracts import Decision, DecisionResult


class StabilityDisposition(StrEnum):
    PROCEED = "PROCEED"
    LOCAL_ONLY = "LOCAL_ONLY"
    DEFER = "DEFER"
    RECONCILE = "RECONCILE"
    DENY = "DENY"


@dataclass(frozen=True)
class RuntimeState:
    online: bool = True
    reconnecting: bool = False
    provider_available: bool = True
    provider_required: bool = False
    river_remote_available: bool = True
    local_evidence_buffer_available: bool = True
    credential_valid: bool = True
    clock_fresh: bool = True
    recovery_mode: bool = False
    interrupted_execution: bool = False
    uncertain_external_effect: bool = False
    location_scope_valid: bool = True


@dataclass(frozen=True)
class StabilityAssessment:
    passed: bool
    disposition: StabilityDisposition
    reason_codes: tuple[str, ...]
    execution_authority_granted: bool = False


class WardenStabilityGate:
    """Checks whether existing Warden authority remains usable in the current runtime state.

    This gate never creates or extends authority. A successful assessment only means the
    already-issued Warden decision remains operationally usable under the tested state.
    """

    def assess(
        self,
        decision: Decision,
        state: RuntimeState,
        now: datetime,
    ) -> StabilityAssessment:
        reasons: list[str] = []

        if decision.result is not DecisionResult.PERMIT:
            return self._deny("WARDEN_DECISION_NOT_PERMITTED")

        try:
            valid_until = datetime.fromisoformat(decision.valid_until)
        except ValueError:
            return self._deny("WARDEN_DECISION_TIME_INVALID")

        if valid_until <= now:
            return self._deny("WARDEN_AUTHORITY_EXPIRED")

        if not state.credential_valid:
            return self._deny("CREDENTIAL_EXPIRED")

        if not state.clock_fresh:
            return StabilityAssessment(
                passed=False,
                disposition=StabilityDisposition.DEFER,
                reason_codes=("CLOCK_STALE",),
            )

        if not state.location_scope_valid:
            return self._deny("LOCATION_SCOPE_INVALID")

        if state.uncertain_external_effect:
            return StabilityAssessment(
                passed=False,
                disposition=StabilityDisposition.RECONCILE,
                reason_codes=("UNCERTAIN_EXTERNAL_EFFECT",),
            )

        if state.reconnecting:
            return StabilityAssessment(
                passed=False,
                disposition=StabilityDisposition.RECONCILE,
                reason_codes=("RECONNECT_RECONCILIATION_REQUIRED",),
            )

        if state.recovery_mode:
            return StabilityAssessment(
                passed=False,
                disposition=StabilityDisposition.RECONCILE,
                reason_codes=("RECOVERY_RECONCILIATION_REQUIRED",),
            )

        if state.interrupted_execution:
            return StabilityAssessment(
                passed=False,
                disposition=StabilityDisposition.DEFER,
                reason_codes=("INTERRUPTED_EXECUTION_REVIEW_REQUIRED",),
            )

        if not state.river_remote_available:
            if not state.local_evidence_buffer_available:
                return self._deny("EVIDENCE_PATH_UNAVAILABLE")
            reasons.append("LOCAL_EVIDENCE_BUFFER_REQUIRED")

        if not state.online:
            if not state.local_evidence_buffer_available:
                return self._deny("OFFLINE_EVIDENCE_BUFFER_UNAVAILABLE")
            if state.provider_required:
                return StabilityAssessment(
                    passed=False,
                    disposition=StabilityDisposition.DEFER,
                    reason_codes=("OFFLINE_PROVIDER_REQUIRED",),
                )
            reasons.append("OFFLINE_LOCAL_ONLY")

        if not state.provider_available:
            if state.provider_required:
                return StabilityAssessment(
                    passed=False,
                    disposition=StabilityDisposition.DEFER,
                    reason_codes=("REQUIRED_PROVIDER_UNAVAILABLE",),
                )
            reasons.append("PROVIDER_UNAVAILABLE_LOCAL_ONLY")

        if reasons:
            return StabilityAssessment(
                passed=True,
                disposition=StabilityDisposition.LOCAL_ONLY,
                reason_codes=tuple(reasons),
            )

        return StabilityAssessment(
            passed=True,
            disposition=StabilityDisposition.PROCEED,
            reason_codes=("STABILITY_CHECK_PASSED",),
        )

    @staticmethod
    def _deny(reason: str) -> StabilityAssessment:
        return StabilityAssessment(
            passed=False,
            disposition=StabilityDisposition.DENY,
            reason_codes=(reason,),
        )
