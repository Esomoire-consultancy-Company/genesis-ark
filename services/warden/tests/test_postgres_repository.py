from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta

from warden_service.evidence import build_evidence_event, utcnow
from warden_service.models import (
    CapabilityGrant,
    CapabilityStatus,
    DecisionOutcome,
    DecisionRecord,
    PolicyDecision,
    PolicyDecisionRequest,
    Revocation,
)
from warden_service.postgres_repository import PostgresRegistry


class FakeCursor:
    def __init__(self, responses: list[object | None]) -> None:
        self.responses = responses
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 1
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql: str, params=()) -> None:
        self.executed.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.responses.pop(0) if self.responses else None

    def fetchall(self):
        value = self.responses.pop(0) if self.responses else []
        return value or []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.transactions = 0

    def cursor(self):
        return self._cursor

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield


class FakePool:
    def __init__(self, responses: list[object | None]) -> None:
        self.cursor = FakeCursor(responses)
        self.connection_object = FakeConnection(self.cursor)
        self.connections = 0

    @contextmanager
    def connection(self, timeout=None):
        self.connections += 1
        yield self.connection_object


def request() -> PolicyDecisionRequest:
    now = utcnow()
    return PolicyDecisionRequest(
        request_id="REQUEST-UNBOUND-001",
        requested_at=now,
        box_id="BOX-UNKNOWN-001",
        runtime_id="RUNTIME-UNKNOWN-001",
        subject_id="DIGITALME-UNKNOWN-001",
        context_id="CONTEXT-UNKNOWN-001",
        resource_id="RESOURCE-UNKNOWN-001",
        requested_action="BROWSER_SESSION_START",
        purpose="TEST",
        data_classes=[],
        requested_duration_seconds=60,
        human_approval_present=False,
    )


def test_unbound_deny_decision_and_evidence_share_one_transaction() -> None:
    item = request()
    event = build_evidence_event(
        box_id=item.box_id,
        event_type="POLICY_DECISION",
        actor_id=item.subject_id,
        context_id=item.context_id,
        action_reference=item.request_id,
        policy_decision="DENY",
        payload={"reason_codes": ["BOX_NOT_FOUND"]},
        previous_event_hash=None,
    )
    decision = PolicyDecision(
        policy_decision_id="DECISION-UNBOUND-001",
        request_id=item.request_id,
        decided_at=event.timestamp,
        outcome=DecisionOutcome.DENY,
        reason_codes=["BOX_NOT_FOUND"],
        policy_bundle_version="warden-v1",
        evidence_event_id=event.event_id,
    )
    pool = FakePool([None, None])
    repository = PostgresRegistry("", pool=pool)

    repository.record_decision(DecisionRecord(decision=decision, request=item), event)

    sql = "\n".join(statement for statement, _ in pool.cursor.executed)
    assert pool.connections == 1
    assert "insert into warden_unbound_evidence_events" in sql
    assert "insert into warden_unbound_decisions" in sql
    assert "insert into warden_policy_decisions" not in sql


def test_capability_revocation_updates_state_and_evidence_atomically() -> None:
    now = utcnow()
    capability = CapabilityGrant(
        capability_id="CAPABILITY-POSTGRES-001",
        box_id="BOX-POSTGRES-001",
        subject_id="DIGITALME-POSTGRES-001",
        resource_id="RESOURCE-POSTGRES-001",
        allowed_action="READ",
        purpose="TEST",
        context_id="CONTEXT-POSTGRES-001",
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5),
        policy_decision_id="DECISION-POSTGRES-001",
        capability_status=CapabilityStatus.ISSUED,
        constraints={},
    )
    previous_hash = "a" * 64
    event = build_evidence_event(
        box_id=capability.box_id,
        event_type="CAPABILITY_REVOKED",
        actor_id=capability.subject_id,
        context_id=capability.context_id,
        action_reference=capability.capability_id,
        policy_decision="REVOKE",
        payload={"reason": "test"},
        previous_event_hash=previous_hash,
    )
    revocation = Revocation(
        revocation_id="REVOCATION-POSTGRES-001",
        box_id=capability.box_id,
        target_type="CAPABILITY",
        target_id=capability.capability_id,
        reason="test",
        revoked_by=capability.subject_id,
        effective_at=now,
        policy_reference="POLICY-REVOCATION-001",
        evidence_event_id=event.event_id,
    )
    pool = FakePool([
        {"capability_status": "ISSUED"},
        {"evidence_hash": previous_hash},
    ])
    repository = PostgresRegistry("", pool=pool)

    repository.revoke_capability(capability.capability_id, revocation, event)

    sql = "\n".join(statement for statement, _ in pool.cursor.executed)
    assert pool.connections == 1
    assert "insert into box_evidence_events" in sql
    assert "update capability_grants" in sql
    assert "insert into box_revocations" in sql
