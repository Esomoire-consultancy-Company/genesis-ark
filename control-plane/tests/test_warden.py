from datetime import datetime, timezone
from pathlib import Path

from genesis_control_plane.contracts import Command, DecisionResult
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.warden import Warden, WardenPolicy

REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
NOW = datetime(2026, 9, 9, 2, 40, tzinfo=timezone.utc)


def command(**changes):
    values = dict(
        command_id="CMD-001",
        correlation_id="CORR-001",
        principal_id="DM-001",
        session_id="SES-001",
        station_id="GES-ALPHA-001",
        adapter_id="GEN-ADAPTER-DOCKER-001",
        target_resource_id="RES-RIVER-WORKER-001",
        capability="container.instance.restart",
        parameters={"timeout_seconds": 30},
        risk_class="medium",
        environment="alpha",
        requested_at="2026-09-09T08:10:00+05:30",
        expires_at="2026-09-09T08:12:00+05:30",
    )
    values.update(changes)
    return Command(**values)


def engine():
    return Warden(AlphaRegistry.load(REGISTRY), WardenPolicy())


def test_known_alpha_restart_is_permitted():
    decision = engine().evaluate(command(), NOW)
    assert decision.result is DecisionResult.PERMIT
    assert decision.reason_code == "PERMITTED"
    assert "evidence_required" in decision.obligations


def test_unknown_target_is_denied():
    decision = engine().evaluate(command(target_resource_id="RES-UNKNOWN"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "UNKNOWN_TARGET"


def test_unknown_capability_is_denied():
    decision = engine().evaluate(command(capability="container.instance.delete"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "UNKNOWN_CAPABILITY"


def test_production_is_denied():
    decision = engine().evaluate(command(environment="production"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "ENVIRONMENT_DENIED"


def test_wrong_station_is_denied():
    decision = engine().evaluate(command(station_id="GES-OTHER"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "STATION_DENIED"


def test_high_risk_is_denied():
    decision = engine().evaluate(command(risk_class="high"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "RISK_DENIED"


def test_expired_command_is_denied():
    decision = engine().evaluate(
        command(expires_at="2026-09-09T02:39:59+00:00"),
        NOW,
    )
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "COMMAND_EXPIRED"


def test_permit_validity_never_outlives_command():
    decision = engine().evaluate(
        command(expires_at="2026-09-09T02:40:10+00:00"),
        NOW,
    )
    assert datetime.fromisoformat(decision.valid_until) <= datetime.fromisoformat(
        "2026-09-09T02:40:10+00:00"
    )


def test_invalid_command_expiry_is_denied_without_exception():
    decision = engine().evaluate(command(expires_at="not-a-time"), NOW)
    assert decision.result is DecisionResult.DENY
    assert decision.reason_code == "COMMAND_TIME_INVALID"
