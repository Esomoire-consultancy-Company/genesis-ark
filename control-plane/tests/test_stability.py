from datetime import datetime, timedelta, timezone

import pytest

from genesis_control_plane.contracts import Decision, DecisionResult
from genesis_control_plane.stability import (
    RuntimeState,
    StabilityDisposition,
    WardenStabilityGate,
)

NOW = datetime(2026, 9, 26, 4, 40, tzinfo=timezone.utc)


def permit(**changes):
    values = dict(
        decision_id="WD-STABILITY-001",
        command_id="CMD-STABILITY-001",
        result=DecisionResult.PERMIT,
        policy_id="WARDEN-ENGINEERING-R0.1",
        conditions=("alpha_only", "one_shot_token"),
        obligations=("evidence_required",),
        decided_at=NOW.isoformat(),
        valid_until=(NOW + timedelta(seconds=60)).isoformat(),
        reason_code="PERMITTED",
    )
    values.update(changes)
    return Decision(**values)


@pytest.mark.parametrize(
    ("name", "state", "passed", "disposition", "reason"),
    [
        ("online", RuntimeState(), True, StabilityDisposition.PROCEED, "STABILITY_CHECK_PASSED"),
        (
            "offline-local",
            RuntimeState(online=False),
            True,
            StabilityDisposition.LOCAL_ONLY,
            "OFFLINE_LOCAL_ONLY",
        ),
        (
            "provider-outage-local",
            RuntimeState(provider_available=False),
            True,
            StabilityDisposition.LOCAL_ONLY,
            "PROVIDER_UNAVAILABLE_LOCAL_ONLY",
        ),
        (
            "provider-required-outage",
            RuntimeState(provider_available=False, provider_required=True),
            False,
            StabilityDisposition.DEFER,
            "REQUIRED_PROVIDER_UNAVAILABLE",
        ),
        (
            "reconnecting",
            RuntimeState(reconnecting=True),
            False,
            StabilityDisposition.RECONCILE,
            "RECONNECT_RECONCILIATION_REQUIRED",
        ),
        (
            "credential-expired",
            RuntimeState(credential_valid=False),
            False,
            StabilityDisposition.DENY,
            "CREDENTIAL_EXPIRED",
        ),
        (
            "clock-stale",
            RuntimeState(clock_fresh=False),
            False,
            StabilityDisposition.DEFER,
            "CLOCK_STALE",
        ),
        (
            "interrupted",
            RuntimeState(interrupted_execution=True),
            False,
            StabilityDisposition.DEFER,
            "INTERRUPTED_EXECUTION_REVIEW_REQUIRED",
        ),
        (
            "uncertain-effect",
            RuntimeState(uncertain_external_effect=True),
            False,
            StabilityDisposition.RECONCILE,
            "UNCERTAIN_EXTERNAL_EFFECT",
        ),
        (
            "recovery",
            RuntimeState(recovery_mode=True),
            False,
            StabilityDisposition.RECONCILE,
            "RECOVERY_RECONCILIATION_REQUIRED",
        ),
        (
            "wrong-location",
            RuntimeState(location_scope_valid=False),
            False,
            StabilityDisposition.DENY,
            "LOCATION_SCOPE_INVALID",
        ),
        (
            "river-down-buffer-ok",
            RuntimeState(river_remote_available=False),
            True,
            StabilityDisposition.LOCAL_ONLY,
            "LOCAL_EVIDENCE_BUFFER_REQUIRED",
        ),
        (
            "river-down-no-buffer",
            RuntimeState(
                river_remote_available=False,
                local_evidence_buffer_available=False,
            ),
            False,
            StabilityDisposition.DENY,
            "EVIDENCE_PATH_UNAVAILABLE",
        ),
    ],
)
def test_runtime_state_matrix(name, state, passed, disposition, reason):
    assessment = WardenStabilityGate().assess(permit(), state, NOW)
    assert assessment.passed is passed, name
    assert assessment.disposition is disposition, name
    assert reason in assessment.reason_codes, name
    assert assessment.execution_authority_granted is False


def test_expired_warden_authority_is_never_extended():
    decision = permit(valid_until=(NOW - timedelta(seconds=1)).isoformat())
    assessment = WardenStabilityGate().assess(decision, RuntimeState(), NOW)
    assert assessment.passed is False
    assert assessment.disposition is StabilityDisposition.DENY
    assert assessment.reason_codes == ("WARDEN_AUTHORITY_EXPIRED",)
    assert assessment.execution_authority_granted is False


def test_denied_warden_decision_can_never_be_upgraded_by_stability_gate():
    decision = permit(result=DecisionResult.DENY, reason_code="RISK_DENIED")
    assessment = WardenStabilityGate().assess(decision, RuntimeState(), NOW)
    assert assessment.passed is False
    assert assessment.reason_codes == ("WARDEN_DECISION_NOT_PERMITTED",)
    assert assessment.execution_authority_granted is False


def test_offline_provider_dependent_execution_defers():
    assessment = WardenStabilityGate().assess(
        permit(),
        RuntimeState(online=False, provider_required=True),
        NOW,
    )
    assert assessment.passed is False
    assert assessment.disposition is StabilityDisposition.DEFER
    assert assessment.reason_codes == ("OFFLINE_PROVIDER_REQUIRED",)


def test_offline_without_evidence_buffer_is_denied():
    assessment = WardenStabilityGate().assess(
        permit(),
        RuntimeState(online=False, local_evidence_buffer_available=False),
        NOW,
    )
    assert assessment.passed is False
    assert assessment.disposition is StabilityDisposition.DENY
    assert assessment.reason_codes == ("OFFLINE_EVIDENCE_BUFFER_UNAVAILABLE",)
