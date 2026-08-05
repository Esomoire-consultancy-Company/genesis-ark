from __future__ import annotations

from warden_service.config import Settings
from warden_service.engine import WardenEngine
from warden_service.models import PolicyDecisionRequest, RuntimeIntegrity
from warden_service.repository import InMemoryRegistry

from conftest import decision_request, seeded_registry


def test_missing_registry_state_denies_and_emits_evidence() -> None:
    registry = InMemoryRegistry()
    engine = WardenEngine(registry, Settings(api_token="test-token"))

    decision = engine.evaluate(PolicyDecisionRequest.model_validate(decision_request()))

    assert decision.outcome == "DENY"
    assert decision.reason_codes == ["BOX_NOT_FOUND"]
    assert registry.latest_evidence(decision_request()["box_id"]) is not None


def test_valid_human_action_is_allowed() -> None:
    registry = seeded_registry()
    engine = WardenEngine(registry, Settings(api_token="test-token"))

    decision = engine.evaluate(
        PolicyDecisionRequest.model_validate(decision_request(agent=False))
    )

    assert decision.outcome == "ALLOW"
    assert decision.capability is not None
    assert decision.capability.subject_id == decision_request(agent=False)["subject_id"]
    assert decision.capability.allowed_action == "READ_AND_RECONCILE"


def test_agent_write_potential_without_approval_is_restricted() -> None:
    registry = seeded_registry()
    engine = WardenEngine(registry, Settings(api_token="test-token"))

    decision = engine.evaluate(PolicyDecisionRequest.model_validate(decision_request()))

    assert decision.outcome == "RESTRICT"
    assert decision.required_approval == "HUMAN_APPROVAL_FOR_WRITE"
    assert decision.capability is not None
    assert decision.capability.allowed_action == "READ_ONLY"
    assert decision.capability.constraints["write_requires_human_approval"] is True


def test_unattested_runtime_denies() -> None:
    registry = seeded_registry()
    runtime = registry.runtimes[decision_request()["runtime_id"]]
    registry.runtimes[runtime.runtime_id] = runtime.model_copy(
        update={"integrity_status": RuntimeIntegrity.FAILED}
    )
    engine = WardenEngine(registry, Settings(api_token="test-token"))

    decision = engine.evaluate(PolicyDecisionRequest.model_validate(decision_request()))

    assert decision.outcome == "DENY"
    assert "RUNTIME_FAILED" in decision.reason_codes


def test_missing_boundary_rule_denies_cross_zone_data() -> None:
    registry = seeded_registry()
    registry.boundaries.clear()
    engine = WardenEngine(registry, Settings(api_token="test-token"))

    decision = engine.evaluate(PolicyDecisionRequest.model_validate(decision_request()))

    assert decision.outcome == "DENY"
    assert "DATA_BOUNDARY_DENIED" in decision.reason_codes
