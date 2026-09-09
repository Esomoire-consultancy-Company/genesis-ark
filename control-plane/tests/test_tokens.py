from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64

import pytest

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.contracts import Command, DecisionResult
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.tokens import TokenIssuer, TokenValidationError
from genesis_control_plane.warden import Warden, WardenPolicy

REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
NOW = datetime(2026, 9, 9, 2, 40, tzinfo=timezone.utc)


def command():
    return Command(
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


def permit(cmd=None):
    cmd = cmd or command()
    return Warden(AlphaRegistry.load(REGISTRY), WardenPolicy()).evaluate(cmd, NOW)


def issuer(audience="WEG-GES-ALPHA-001"):
    return TokenIssuer(b"test-secret", "KEY-TEST-001", audience)


def test_permit_produces_valid_bound_claims():
    cmd = command()
    token = issuer().issue(cmd, permit(cmd), NOW, ttl_seconds=60)
    claims = issuer().decode_and_verify(token, NOW + timedelta(seconds=1))
    assert claims.command_id == cmd.command_id
    assert claims.max_uses == 1
    assert claims.parameters_hash == sha256_hex(canonical_json(dict(cmd.parameters)))


def test_modified_payload_fails_signature_validation():
    token = issuer().issue(command(), permit(), NOW)
    payload, signature = token.split(".")
    raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    changed = raw.replace(b"RES-RIVER-WORKER-001", b"RES-RIVER-WORKER-999")
    changed_payload = base64.urlsafe_b64encode(changed).rstrip(b"=").decode()
    with pytest.raises(TokenValidationError) as exc:
        issuer().decode_and_verify(f"{changed_payload}.{signature}", NOW)
    assert exc.value.code == "INVALID_SIGNATURE"


def test_expired_token_fails():
    token = issuer().issue(command(), permit(), NOW, ttl_seconds=1)
    with pytest.raises(TokenValidationError) as exc:
        issuer().decode_and_verify(token, NOW + timedelta(seconds=2))
    assert exc.value.code == "TOKEN_EXPIRED"


def test_wrong_audience_fails():
    token = issuer().issue(command(), permit(), NOW)
    with pytest.raises(TokenValidationError) as exc:
        issuer("WEG-OTHER").decode_and_verify(token, NOW)
    assert exc.value.code == "AUDIENCE_MISMATCH"


def test_deny_decision_cannot_issue_token():
    cmd = replace(command(), environment="production")
    decision = Warden(AlphaRegistry.load(REGISTRY), WardenPolicy()).evaluate(cmd, NOW)
    assert decision.result is DecisionResult.DENY
    with pytest.raises(TokenValidationError) as exc:
        issuer().issue(cmd, decision, NOW)
    assert exc.value.code == "DECISION_NOT_PERMIT"
