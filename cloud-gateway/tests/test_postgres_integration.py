"""Real PostgreSQL contract tests, run only when GENESIS_TEST_ADMIN_DATABASE_URL is set."""
from __future__ import annotations

import os
import secrets
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from genesis_gateway.ledger import IntentConflict, PostgresLedger
from genesis_gateway.provision import provision_staging


@pytest.fixture(scope="module")
def provisioned():
    admin = os.getenv("GENESIS_TEST_ADMIN_DATABASE_URL")
    if not admin:
        pytest.skip("Requires isolated PostgreSQL CI service")
    role = "genesis_gateway_ci_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(40)
    provision_staging(admin, role, password)
    runtime = make_conninfo(admin, user=role, password=password)
    yield admin, runtime, role
    # In isolated ephemeral CI DB, cleanup only the role. The fixture's DB is deleted
    # with the CI service; production or Railway DBs are never passed to this fixture.


def test_runtime_role_is_unprivileged_and_ready(provisioned):
    admin, runtime, role = provisioned
    assert PostgresLedger(runtime).ready() is True
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = %s",
            (role,),
        )
        assert cur.fetchone() == (False, False, False, False)


def test_insert_and_idempotent_denial_with_real_db(provisioned):
    _, runtime, _ = provisioned
    ledger = PostgresLedger(runtime)
    req = {
        "request_id": str(uuid4()),
        "correlation_id": "COR-CI-001",
        "target_resource_id": "RES-CI-001",
        "capability": "container.instance.restart",
    }
    receipt = ledger.record_denial(req, "DIGITALME-ACTOR-CI")
    assert receipt["result"] == "DENY"
    assert receipt["execution_invoked"] is False
    assert len(receipt["evidence_hash"]) == 64
    assert ledger.record_denial(req, "DIGITALME-ACTOR-CI") == receipt
    with pytest.raises(IntentConflict):
        ledger.record_denial({**req, "capability": "different.scope"}, "DIGITALME-ACTOR-CI")


def test_runtime_role_cannot_update_or_delete_evidence(provisioned):
    _, runtime, _ = provisioned
    with psycopg.connect(runtime) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE public.gateway_evidence SET event = '{}'::jsonb")
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM public.gateway_evidence")
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("CREATE TABLE public.not_permitted (id bigint)")


def test_gateway_evidence_hash_chain_across_distinct_intents(provisioned):
    admin, runtime, _ = provisioned
    ledger = PostgresLedger(runtime)
    for i in range(2):
        ledger.record_denial({
            "request_id": str(uuid4()),
            "correlation_id": f"COR-CI-{i}",
            "target_resource_id": "RES-CI-001",
            "capability": "container.instance.restart",
        }, "DIGITALME-ACTOR-CI")
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute("SELECT event, record_hash, previous_hash FROM public.gateway_evidence ORDER BY seq ASC")
        rows = cur.fetchall()
    from genesis_gateway.ledger import hash_record
    previous = None
    for event, digest, parent in rows:
        assert parent == previous
        assert hash_record(event, parent) == digest
        previous = digest
