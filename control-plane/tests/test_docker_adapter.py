import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from genesis_control_plane.contracts import Command, ExecutionState, VerificationState
from genesis_control_plane.docker_adapter import DockerAdapter, UnsupportedCapabilityError
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.verifier import DockerVerifier

REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"
NOW = datetime(2026, 9, 9, 2, 45, tzinfo=timezone.utc)


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return self.responses.pop(0)


def result(code=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def command(capability="container.instance.restart", timeout=30):
    return Command(
        command_id="CMD-001",
        correlation_id="CORR-001",
        principal_id="DM-001",
        session_id="SES-001",
        station_id="GES-ALPHA-001",
        adapter_id="GEN-ADAPTER-DOCKER-001",
        target_resource_id="RES-RIVER-WORKER-001",
        capability=capability,
        parameters={"timeout_seconds": timeout},
        risk_class="medium",
        environment="alpha",
        requested_at=NOW.isoformat(),
        expires_at=NOW.isoformat(),
    )


def resource():
    return AlphaRegistry.load(REGISTRY).resource("RES-RIVER-WORKER-001")


def test_restart_uses_exact_bounded_argument_vector():
    runner = FakeRunner([result(stdout="river-worker\n")])
    execution = DockerAdapter(runner=runner).restart(resource(), command(), NOW)
    assert runner.calls[0][0] == ["docker", "restart", "--timeout", "30", "river-worker"]
    assert runner.calls[0][1]["shell"] is False
    assert execution.state is ExecutionState.COMPLETED


def test_inspect_uses_registered_docker_name():
    payload = [{"Name": "/river-worker", "State": {"Running": True}}]
    runner = FakeRunner([result(stdout=json.dumps(payload))])
    data = DockerAdapter(runner=runner).inspect(resource())
    assert runner.calls[0][0] == ["docker", "inspect", "river-worker"]
    assert data[0]["State"]["Running"] is True


def test_unsupported_capability_never_calls_runner():
    runner = FakeRunner([])
    with pytest.raises(UnsupportedCapabilityError):
        DockerAdapter(runner=runner).restart(resource(), command("container.instance.delete"), NOW)
    assert runner.calls == []


@pytest.mark.parametrize("timeout", [0, 301, -1])
def test_timeout_is_bounded(timeout):
    runner = FakeRunner([])
    with pytest.raises(ValueError, match="INVALID_TIMEOUT"):
        DockerAdapter(runner=runner).restart(resource(), command(timeout=timeout), NOW)
    assert runner.calls == []


def test_verifier_requires_running_and_healthy_when_healthcheck_exists():
    inspect_payload = [{
        "Name": "/river-worker",
        "State": {"Running": True, "Health": {"Status": "healthy"}},
    }]
    runner = FakeRunner([result(stdout="river-worker\n"), result(stdout=json.dumps(inspect_payload))])
    adapter = DockerAdapter(runner=runner)
    execution = adapter.restart(resource(), command(), NOW)
    verification = DockerVerifier(adapter).verify_restart(resource(), execution, NOW)
    assert verification.state is VerificationState.VERIFIED


def test_verifier_rejects_unhealthy_container():
    inspect_payload = [{
        "Name": "/river-worker",
        "State": {"Running": True, "Health": {"Status": "unhealthy"}},
    }]
    runner = FakeRunner([result(stdout="river-worker\n"), result(stdout=json.dumps(inspect_payload))])
    adapter = DockerAdapter(runner=runner)
    execution = adapter.restart(resource(), command(), NOW)
    verification = DockerVerifier(adapter).verify_restart(resource(), execution, NOW)
    assert verification.state is VerificationState.NOT_VERIFIED
