"""Real PostgreSQL contract tests, run only when GENESIS_TEST_ADMIN_DATABASE_URL is set."""
from __future__ import annotations

import os
import secrets
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from psycopg import sql

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
    try:
        yield admin, runtime, role
    finally:
        # Never leave a reusable LOGIN principal even in an ephemeral test DB.
        with psycopg.connect(admin) as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("REVOKE ALL ON TABLE public.gateway_evidence FROM {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("REVOKE ALL ON SEQUENCE public.gateway_evidence_seq_seq FROM {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_runtime_role_is_unprivileged_and_ready(provisioned):
    admin, runtime, role = provisioned
    assert PostgresLedger(runtime).ready() is True
    # A superuser can read and write, but must never pass gateway readiness.
    assert PostgresLedger(admin).ready() is False
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


def test_concurrent_replays_write_one_record(provisioned):
    from concurrent.futures import ThreadPoolExecutor

    admin, runtime, _ = provisioned
    request_id = str(uuid4())
    intent = {
        "request_id": request_id,
        "correlation_id": "COR-CONCURRENT",
        "target_resource_id": "RES-CI-001",
        "capability": "container.instance.restart",
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(
            lambda _: PostgresLedger(runtime).record_denial(intent, "DIGITALME-ACTOR-CI"),
            range(4),
        ))
    assert all(receipt == receipts[0] for receipt in receipts)
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.gateway_evidence WHERE request_id = %s", (request_id,))
        assert cur.fetchone()[0] == 1



def test_runtime_column_update_grant_is_rejected(provisioned):
    from psycopg import sql
    admin, runtime, role = provisioned
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("GRANT UPDATE(event) ON TABLE public.gateway_evidence TO {}").format(sql.Identifier(role)))
    try:
        assert PostgresLedger(runtime).ready() is False
    finally:
        with psycopg.connect(admin) as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("REVOKE UPDATE(event) ON TABLE public.gateway_evidence FROM {}").format(sql.Identifier(role)))
    assert PostgresLedger(runtime).ready() is True


def test_runtime_set_capable_privileged_role_rejected(provisioned):
    from psycopg import sql
    admin, runtime, role = provisioned
    elevated = "genesis_gateway_priv_" + secrets.token_hex(4)
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN CREATEDB").format(sql.Identifier(elevated)))
        cur.execute(sql.SQL("GRANT {} TO {} WITH SET TRUE").format(sql.Identifier(elevated), sql.Identifier(role)))
    try:
        assert PostgresLedger(runtime).ready() is False
    finally:
        with psycopg.connect(admin) as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(elevated), sql.Identifier(role)))
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(elevated)))
    assert PostgresLedger(runtime).ready() is True


def test_gateway_append_only_blocks_owner_mutation(provisioned):
    admin, runtime, _ = provisioned
    ledger = PostgresLedger(runtime)
    ledger.record_denial({
        "request_id": str(uuid4()), "correlation_id": "IMMUTABLE-CI",
        "target_resource_id": "RES-TEST-ONLY",
        "capability": "container.instance.restart",
    }, "DIGITALME-ACTOR-CI")
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.RaiseException, match="GATEWAY_EVIDENCE_APPEND_ONLY"):
            cur.execute("UPDATE public.gateway_evidence SET event = event")
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException, match="GATEWAY_EVIDENCE_APPEND_ONLY"):
            cur.execute("TRUNCATE public.gateway_evidence")
        conn.rollback()


def test_database_bound_rate_limit_and_replay(provisioned, monkeypatch):
    from genesis_gateway import ledger as ledger_module
    from genesis_gateway.ledger import CapacityExceeded
    _, runtime, _ = provisioned
    gateway = PostgresLedger(runtime)
    intent = {
        "request_id": str(uuid4()), "correlation_id": "RATE-CI",
        "target_resource_id": "RES-TEST-ONLY", "capability": "container.instance.restart",
    }
    receipt = gateway.record_denial(intent, "DIGITALME-ACTOR-CI")
    monkeypatch.setattr(ledger_module, "MAX_NEW_INTENTS_PER_MINUTE", 0)
    assert gateway.record_denial(intent, "DIGITALME-ACTOR-CI") == receipt
    with pytest.raises(CapacityExceeded, match="INTENT_RATE_LIMIT"):
        gateway.record_denial({**intent, "request_id": str(uuid4())}, "DIGITALME-ACTOR-CI")
    monkeypatch.setattr(ledger_module, "MAX_NEW_INTENTS_PER_MINUTE", 60)
    monkeypatch.setattr(ledger_module, "MAX_SPOOL_ROWS", 0)
    with pytest.raises(CapacityExceeded, match="EVIDENCE_SPOOL_FULL"):
        gateway.record_denial({**intent, "request_id": str(uuid4())}, "DIGITALME-ACTOR-CI")


def test_independent_auditor_rejects_overprivileged_roles(provisioned):
    from psycopg import sql
    from genesis_gateway.provision import scram_verifier
    from genesis_gateway.spool_integrity import verify_database, EvidenceIntegrityError
    admin, runtime, _ = provisioned
    name = "genesis_gateway_audit_" + secrets.token_hex(4)
    password = secrets.token_urlsafe(40)
    with psycopg.connect(admin) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}").format(
            sql.Identifier(name), sql.Literal(scram_verifier(password))))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(name)))
        cur.execute(sql.SQL("GRANT SELECT ON TABLE public.gateway_evidence TO {}").format(sql.Identifier(name)))
    auditor = make_conninfo(admin, user=name, password=password)
    try:
        with pytest.raises(EvidenceIntegrityError, match="AUDIT_ROLE_NOT_READONLY"):
            verify_database(admin)
        # The role has only SELECT, independent of the gateway's INSERT capability.
        assert verify_database(auditor)["external_witnessed"] is False
        for statement, undo in [
            ("GRANT TRIGGER ON TABLE public.gateway_evidence TO {}", "REVOKE TRIGGER ON TABLE public.gateway_evidence FROM {}"),
            ("GRANT pg_read_all_data TO {}", "REVOKE pg_read_all_data FROM {}"),
            ("GRANT UPDATE ON SEQUENCE public.gateway_evidence_seq_seq TO {}", "REVOKE UPDATE ON SEQUENCE public.gateway_evidence_seq_seq FROM {}"),
        ]:
            with psycopg.connect(admin) as conn, conn.cursor() as cur:
                cur.execute(sql.SQL(statement).format(sql.Identifier(name)))
            try:
                with pytest.raises(EvidenceIntegrityError, match="AUDIT_ROLE_NOT_READONLY"):
                    verify_database(auditor)
            finally:
                with psycopg.connect(admin) as conn, conn.cursor() as cur:
                    cur.execute(sql.SQL(undo).format(sql.Identifier(name)))
    finally:
        with psycopg.connect(admin) as conn, conn.cursor() as cur:
            cur.execute(sql.SQL("REVOKE ALL ON TABLE public.gateway_evidence FROM {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def test_scram_verifier_does_not_expose_plaintext():
    from genesis_gateway.provision import scram_verifier
    password = "fixture-password-" + secrets.token_urlsafe(40)
    a = scram_verifier(password)
    b = scram_verifier(password)
    assert a.startswith("SCRAM-SHA-256$4096:")
    assert password not in a
    assert a != b  # Random salts, same plaintext.
