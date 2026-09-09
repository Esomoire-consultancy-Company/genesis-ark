from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genesis_control_plane.contracts import Command, VerificationState
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.service import GovernedExecutionService
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.verifier import DockerVerifier
from genesis_control_plane.warden import Warden, WardenPolicy
from genesis_control_plane.weg import ConsumedTokenLedger, WardenExecutionGateway, WEGValidationError

pytestmark = pytest.mark.docker_e2e
REGISTRY_PATH = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
NOW = datetime(2026, 9, 9, 3, 0, tzinfo=timezone.utc)
RESOURCE_ID = "RES-GES-TEST-CONTAINER-001"
CONTAINER = "ges-alpha-test"


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    return result.returncode == 0


@pytest.fixture(scope="module")
def docker_fixture():
    if not docker_available():
        pytest.skip("Docker engine unavailable")
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, check=False)
    result = subprocess.run(
        ["docker", "run", "-d", "--name", CONTAINER, "alpine:3.20", "sh", "-c", "while true; do sleep 60; done"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"could not create disposable Docker fixture: {result.stderr.strip()}")
    try:
        yield
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, check=False)


def registry():
    return AlphaRegistry.load(REGISTRY_PATH)


def command(timeout=30):
    return Command(
        command_id="CMD-E2E-001",
        correlation_id="CORR-E2E-001",
        principal_id="DM-E2E",
        session_id="SES-E2E",
        station_id="GES-ALPHA-001",
        adapter_id="GEN-ADAPTER-DOCKER-001",
        target_resource_id=RESOURCE_ID,
        capability="container.instance.restart",
        parameters={"timeout_seconds": timeout},
        risk_class="medium",
        environment="alpha",
        requested_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
    )


def stack(tmp_path):
    reg = registry()
    issuer = TokenIssuer(b"e2e-test-secret", "KEY-E2E-001", "WEG-GES-ALPHA-001")
    warden = Warden(reg, WardenPolicy())
    weg = WardenExecutionGateway(reg, issuer, ConsumedTokenLedger(tmp_path / "tokens.sqlite3"))
    adapter = DockerAdapter()
    evidence = EvidenceJournal(tmp_path / "river.jsonl")
    service = GovernedExecutionService(reg, warden, issuer, weg, adapter, DockerVerifier(adapter), evidence)
    return reg, issuer, warden, weg, evidence, service


def test_registry_contains_disposable_e2e_resource():
    resource = registry().resource(RESOURCE_ID)
    assert resource.docker_name == CONTAINER


def test_authorized_restart_is_verified_and_evidenced(tmp_path, docker_fixture):
    _reg, _issuer, _warden, _weg, evidence, service = stack(tmp_path)
    before = json.loads(subprocess.run(["docker", "inspect", CONTAINER], capture_output=True, text=True, check=True).stdout)[0]["State"]["StartedAt"]
    outcome = service.execute(command(), NOW)
    after = json.loads(subprocess.run(["docker", "inspect", CONTAINER], capture_output=True, text=True, check=True).stdout)[0]["State"]["StartedAt"]
    assert outcome.verification.state is VerificationState.VERIFIED
    assert before != after
    assert evidence.verify_chain()


def test_replay_is_rejected_before_second_execution(tmp_path, docker_fixture):
    reg, issuer, warden, weg, _evidence, _service = stack(tmp_path)
    cmd = command()
    decision = warden.evaluate(cmd, NOW)
    token = issuer.issue(cmd, decision, NOW)
    weg.validate_and_consume(token, cmd, NOW + timedelta(seconds=1))
    with pytest.raises(WEGValidationError) as exc:
        weg.validate_and_consume(token, cmd, NOW + timedelta(seconds=2))
    assert exc.value.code == "REPLAY_DETECTED"


def test_parameter_tampering_is_rejected_before_docker(tmp_path, docker_fixture):
    reg, issuer, warden, weg, _evidence, _service = stack(tmp_path)
    cmd = command(timeout=30)
    token = issuer.issue(cmd, warden.evaluate(cmd, NOW), NOW)
    with pytest.raises(WEGValidationError) as exc:
        weg.validate_and_consume(token, replace(cmd, parameters={"timeout_seconds": 31}), NOW + timedelta(seconds=1))
    assert exc.value.code == "PARAMETERS_MISMATCH"
