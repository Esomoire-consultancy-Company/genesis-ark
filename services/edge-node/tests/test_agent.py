from __future__ import annotations

from datetime import timedelta

from edge_node_service.agent import GenesisEdgeAgent
from edge_node_service.models import CommandType, IssueCommandRequest
from edge_node_service.spool import SQLiteEventSpool
from edge_node_service.supervisor import DeterministicSupervisor


def _agent(tmp_path, enrolled_engine, verifier, secret_resolver):
    return GenesisEdgeAgent(
        node_id="node-001",
        agent_id="edge-agent-001",
        credential_reference="vault:edge/node-001",
        attestation_reference="attestation-001",
        agent_version="1.0.0",
        controller=enrolled_engine,
        capability_verifier=verifier,
        secret_resolver=secret_resolver,
        supervisor=DeterministicSupervisor(),
        spool=SQLiteEventSpool(tmp_path / "edge-spool.sqlite3"),
    )


def test_agent_executes_authorized_command_and_flushes_durable_spool(
    tmp_path,
    enrolled_engine,
    verifier,
    secret_resolver,
    clock,
):
    enrolled_engine.issue_command(
        "node-001",
        IssueCommandRequest(
            command_id="command-agent-001",
            command_type=CommandType.START_INSTANCE,
            capability_id="cap-001",
            issued_by="operator-001",
            target_reference="runtime-001",
            payload={},
            expires_at=clock.value + timedelta(minutes=10),
        ),
    )
    agent = _agent(tmp_path, enrolled_engine, verifier, secret_resolver)
    completed = agent.run_once()
    assert completed is not None
    assert completed.status.value == "SUCCEEDED"
    assert completed.result == {"instance_id": "runtime-001", "state": "RUNNING"}
    assert agent.spool.count() == 2

    reopened = SQLiteEventSpool(tmp_path / "edge-spool.sqlite3")
    assert reopened.count() == 2
    agent.spool = reopened
    receipt = agent.flush_spool()
    assert receipt is not None
    assert receipt.last_sequence == 2
    assert reopened.count() == 0


def test_agent_rechecks_revocation_before_execution(
    tmp_path,
    enrolled_engine,
    verifier,
    secret_resolver,
    clock,
):
    enrolled_engine.issue_command(
        "node-001",
        IssueCommandRequest(
            command_id="command-agent-002",
            command_type=CommandType.EXECUTE_RECOVERY,
            capability_id="cap-005",
            issued_by="operator-001",
            target_reference="runtime-001",
            payload={},
            expires_at=clock.value + timedelta(minutes=10),
        ),
    )
    verifier.revoke("cap-005")
    supervisor = DeterministicSupervisor()
    agent = GenesisEdgeAgent(
        node_id="node-001",
        agent_id="edge-agent-001",
        credential_reference="vault:edge/node-001",
        attestation_reference="attestation-001",
        agent_version="1.0.0",
        controller=enrolled_engine,
        capability_verifier=verifier,
        secret_resolver=secret_resolver,
        supervisor=supervisor,
        spool=SQLiteEventSpool(tmp_path / "revoked.sqlite3"),
    )
    completed = agent.run_once()
    assert completed is not None
    assert completed.status.value == "FAILED"
    assert "CAPABILITY_INACTIVE" in completed.result["reason_codes"]
    assert supervisor.instances == {}


def test_agent_heartbeat_sequence_survives_restart(
    tmp_path,
    enrolled_engine,
    verifier,
    secret_resolver,
    clock,
):
    agent = _agent(tmp_path, enrolled_engine, verifier, secret_resolver)
    first = agent.send_heartbeat(sent_at=clock.value)
    assert first.sequence == 1

    clock.advance(seconds=5)
    restarted = _agent(tmp_path, enrolled_engine, verifier, secret_resolver)
    second = restarted.send_heartbeat(sent_at=clock.value)
    assert second.sequence == 2
