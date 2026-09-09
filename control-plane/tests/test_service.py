import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from genesis_control_plane.contracts import Command, DecisionResult, VerificationState
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.service import GovernedExecutionService
from genesis_control_plane.verifier import DockerVerifier

NOW = datetime(2026, 9, 9, 2, 50, tzinfo=timezone.utc)


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[:2] == ["docker", "restart"]:
            return SimpleNamespace(returncode=0, stdout="river-worker\n", stderr="")
        if args[:2] == ["docker", "inspect"]:
            payload = [{
                "Name": "/river-worker",
                "State": {"Running": True, "Health": {"Status": "healthy"}},
            }]
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(args)


def command(environment="alpha"):
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
        environment=environment,
        requested_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
    )


def make_service(registry, warden, token_issuer, weg, evidence, runner):
    adapter = DockerAdapter(runner=runner)
    return GovernedExecutionService(
        registry=registry,
        warden=warden,
        token_issuer=token_issuer,
        weg=weg,
        adapter=adapter,
        verifier=DockerVerifier(adapter),
        evidence=evidence,
    )


def event_types(evidence):
    return [record["event"]["event_type"] for record in evidence._records()]


def test_successful_governed_execution_records_full_chain(
    registry, warden, token_issuer, weg, evidence
):
    runner = FakeRunner()
    service = make_service(registry, warden, token_issuer, weg, evidence, runner)
    outcome = service.execute(command(), NOW)
    assert outcome.decision.result is DecisionResult.PERMIT
    assert outcome.token_id.startswith("WCT-")
    assert len([call for call in runner.calls if call[0][:2] == ["docker", "restart"]]) == 1
    assert outcome.verification.state is VerificationState.VERIFIED
    assert event_types(evidence) == [
        "command.requested",
        "warden.decision.created",
        "warden.token.issued",
        "weg.token.consumed",
        "execution.completed",
        "verification.completed",
        "river.receipt.completed",
    ]
    records = evidence._records()
    assert {record["event"]["correlation_id"] for record in records} == {"CORR-001"}
    assert evidence.verify_chain()


def test_denied_command_never_reaches_docker(registry, warden, token_issuer, weg, evidence):
    runner = FakeRunner()
    service = make_service(registry, warden, token_issuer, weg, evidence, runner)
    outcome = service.execute(command(environment="production"), NOW)
    assert outcome.decision.result is DecisionResult.DENY
    assert outcome.token_id is None
    assert outcome.execution is None
    assert outcome.verification is None
    assert runner.calls == []
    assert event_types(evidence) == [
        "command.requested",
        "warden.decision.created",
    ]
