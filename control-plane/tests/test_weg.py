from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genesis_control_plane.contracts import Command
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.warden import Warden, WardenPolicy
from genesis_control_plane.weg import ConsumedTokenLedger, WardenExecutionGateway, WEGValidationError

REGISTRY_PATH = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
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
        requested_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
    )
    values.update(changes)
    return Command(**values)


def setup_gateway(tmp_path):
    registry = AlphaRegistry.load(REGISTRY_PATH)
    issuer = TokenIssuer(b"test-secret", "KEY-TEST-001", "WEG-GES-ALPHA-001")
    ledger = ConsumedTokenLedger(tmp_path / "tokens.sqlite3")
    gateway = WardenExecutionGateway(registry, issuer, ledger)
    return registry, issuer, ledger, gateway


def token_for(issuer, registry, cmd):
    decision = Warden(registry, WardenPolicy()).evaluate(cmd, NOW)
    return issuer.issue(cmd, decision, NOW)


def test_valid_token_passes_once_and_replay_is_rejected(tmp_path):
    registry, issuer, ledger, gateway = setup_gateway(tmp_path)
    cmd = command()
    token = token_for(issuer, registry, cmd)
    claims = gateway.validate_and_consume(token, cmd, NOW + timedelta(seconds=1))
    assert ledger.is_consumed(claims.token_id)
    with pytest.raises(WEGValidationError) as exc:
        gateway.validate_and_consume(token, cmd, NOW + timedelta(seconds=2))
    assert exc.value.code == "REPLAY_DETECTED"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"target_resource_id": "RES-UNKNOWN"}, "TARGET_MISMATCH"),
        ({"adapter_id": "GEN-ADAPTER-OTHER-001"}, "ADAPTER_MISMATCH"),
        ({"parameters": {"timeout_seconds": 31}}, "PARAMETERS_MISMATCH"),
        ({"station_id": "GES-OTHER"}, "STATION_MISMATCH"),
        ({"session_id": "SES-OTHER"}, "SESSION_MISMATCH"),
        ({"principal_id": "DM-OTHER"}, "PRINCIPAL_MISMATCH"),
    ],
)
def test_binding_mismatch_is_rejected(tmp_path, changes, code):
    registry, issuer, _ledger, gateway = setup_gateway(tmp_path)
    original = command()
    token = token_for(issuer, registry, original)
    with pytest.raises(WEGValidationError) as exc:
        gateway.validate_and_consume(token, replace(original, **changes), NOW + timedelta(seconds=1))
    assert exc.value.code == code


def test_registry_binding_must_still_be_valid(tmp_path):
    registry, issuer, _ledger, gateway = setup_gateway(tmp_path)
    cmd = command()
    token = token_for(issuer, registry, cmd)
    registry._resources = {}
    with pytest.raises(WEGValidationError) as exc:
        gateway.validate_and_consume(token, cmd, NOW + timedelta(seconds=1))
    assert exc.value.code == "REGISTRY_BINDING_INVALID"
