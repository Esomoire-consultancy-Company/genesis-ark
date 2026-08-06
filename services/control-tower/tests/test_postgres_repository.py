from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta

from control_tower_service.evidence import utcnow
from control_tower_service.postgres_repository import PostgresControlTowerRepository


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.row = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        self.connection.executed.append((normalized, params))
        if "from public.active_capability_grants" in normalized:
            self.row = self.connection.capability_row
        else:
            self.row = None

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, capability_row=None):
        self.executed = []
        self.capability_row = capability_row

    def cursor(self):
        return FakeCursor(self)


class FakePool:
    def __init__(self, connection):
        self.connection_object = connection
        self.connection_calls = 0

    @contextmanager
    def connection(self, timeout=None):
        del timeout
        self.connection_calls += 1
        yield self.connection_object


def test_transaction_reuses_one_connection_and_takes_advisory_lock():
    connection = FakeConnection()
    pool = FakePool(connection)
    repository = PostgresControlTowerRepository("", pool=pool)

    with repository.transaction("incident-fingerprint:abc"):
        repository.save_signal(
            "SIGNAL-001",
            "a" * 64,
            "INCIDENT-001",
        )

    assert pool.connection_calls == 1
    queries = [query for query, _ in connection.executed]
    assert any("pg_advisory_xact_lock" in query for query in queries)
    assert any("insert into genesis_control_tower.operational_signals" in query for query in queries)


def test_postgres_repository_verifies_active_warden_capability():
    expires_at = utcnow() + timedelta(minutes=30)
    connection = FakeConnection(
        capability_row={
            "capability_id": "CAP-CONTROL-001",
            "box_id": "BOX-OPS-001",
            "subject_id": "DIGITALME-OPS-001",
            "context_id": "CONTEXT-OPS-001",
            "resource_id": "NODE-BLR-001",
            "allowed_action": "CONTROL_TOWER_COMMAND_ISSUE",
            "purpose": "operate governed fleet",
            "expires_at": expires_at,
            "constraints": {},
        }
    )
    repository = PostgresControlTowerRepository("", pool=FakePool(connection))

    authorization = repository.verify(
        capability_id="CAP-CONTROL-001",
        box_id="BOX-OPS-001",
        principal_id="DIGITALME-OPS-001",
        context_id="CONTEXT-OPS-001",
        resource_id="NODE-BLR-001",
        required_actions={"CONTROL_TOWER_COMMAND_ISSUE"},
        purpose="operate governed fleet",
        at=utcnow(),
    )

    assert authorization is not None
    assert authorization.expires_at == expires_at
    query = next(
        query
        for query, _ in connection.executed
        if "active_capability_grants" in query
    )
    assert "expires_at > %s" in query


def test_nested_transactions_take_both_advisory_locks_on_one_connection():
    connection = FakeConnection()
    pool = FakePool(connection)
    repository = PostgresControlTowerRepository("", pool=pool)

    with repository.transaction("signal:SIGNAL-001"):
        with repository.transaction("incident-fingerprint:abc"):
            pass

    assert pool.connection_calls == 1
    lock_params = [
        params[0]
        for query, params in connection.executed
        if "pg_advisory_xact_lock" in query
    ]
    assert lock_params == ["signal:SIGNAL-001", "incident-fingerprint:abc"]
