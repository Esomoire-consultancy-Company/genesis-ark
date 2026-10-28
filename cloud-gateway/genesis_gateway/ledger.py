"""PostgreSQL-backed append-only River-compatible evidence draft.

Not a replacement for RiverOS: the schema is a gateway-owned evidence spool.
No executive capability tokens or runtime operations are issued here.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone


LOCK_ID = 72310641  # Serialize this gateway spool's hash chain per database.
DENIAL = "WARDEN_NOT_PROVISIONED"


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_record(event: dict, previous_hash: str | None) -> str:
    material = {"event": event, "previous_hash": previous_hash}
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


class IntentConflict(ValueError):
    """Idempotency key has been reused for a distinct command."""


class PostgresLedger:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        # Import lazily so offline contract tests can run without a database.
        import psycopg
        return psycopg.connect(self.dsn, connect_timeout=3)

    def ready(self) -> bool:
        """A spool table alone is insufficient: reject privileged application DSNs.

        Readiness requires usable SELECT/INSERT/sequence privileges and rejects
        schema CREATE, table mutation, and administrator role attributes.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT
                  to_regclass('public.gateway_evidence') IS NOT NULL,
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'SELECT'), false),
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'INSERT'), false),
                  COALESCE(has_sequence_privilege(current_user,
                    to_regclass('public.gateway_evidence_seq_seq'), 'USAGE'), false),
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'UPDATE'), false),
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'DELETE'), false),
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'TRUNCATE'), false),
                  COALESCE(has_table_privilege(current_user,
                    to_regclass('public.gateway_evidence'), 'TRIGGER'), false),
                  COALESCE(has_sequence_privilege(current_user,
                    to_regclass('public.gateway_evidence_seq_seq'), 'UPDATE'), false),
                  has_schema_privilege(current_user, 'public', 'CREATE'),
                  has_database_privilege(current_user, current_database(), 'CREATE'),
                  pg_has_role(current_user, 'pg_read_all_data', 'member'),
                  pg_has_role(current_user, 'pg_write_all_data', 'member'),
                  (SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                     FROM pg_roles WHERE rolname = current_user)
            """)
            (exists, can_select, can_insert, can_sequence,
             can_update, can_delete, can_truncate, can_trigger,
             can_sequence_update, can_create, can_create_database,
             broad_read, broad_write, privileged) = cur.fetchone()
            return all((exists, can_select, can_insert, can_sequence)) and not any(
                (can_update, can_delete, can_truncate, can_trigger,
                 can_sequence_update, can_create, can_create_database,
                 broad_read, broad_write, privileged)
            )

    def record_denial(self, intent: dict, issuer: str) -> dict:
        """Record a denial before returning it; never dispatch execution.

        All writes take a transaction advisory lock, so sequential hashes remain
        coherent across multiple Railway replicas sharing a PostgreSQL database.
        Existing request_id returns the original receipt only for an identical
        issuer+intent; mismatched idempotency keys produce a conflict.
        """
        with self._connect() as conn, conn.cursor() as cur:
            # Bound lock waits and queries: fail closed under contention.
            cur.execute("SET LOCAL lock_timeout = '3s'")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL search_path = pg_catalog, public")
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
            cur.execute(
                "SELECT event, record_hash, previous_hash FROM public.gateway_evidence WHERE request_id = %s",
                (intent["request_id"],),
            )
            prior = cur.fetchone()
            if prior:
                event, record_hash, previous_hash = prior
                if event["issuer_id"] != issuer or event["intent"] != intent:
                    raise IntentConflict("REQUEST_ID_CONFLICT")
                return _receipt(event, record_hash, previous_hash)

            cur.execute("SELECT record_hash FROM public.gateway_evidence ORDER BY seq DESC LIMIT 1")
            row = cur.fetchone()
            previous_hash = row[0] if row else None
            event = {
                "schema_version": "genesis-gateway-evidence.r0.1",
                "event_id": str(uuid.uuid4()),
                "event_type": "warden.decision.denied",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "issuer_id": issuer,
                "intent": intent,
                "result": "DENY",
                "reason_code": DENIAL,
                "execution_invoked": False,
            }
            record_hash = hash_record(event, previous_hash)
            cur.execute(
                "INSERT INTO public.gateway_evidence (request_id, event_id, event, record_hash, previous_hash) "
                "VALUES (%s, %s, %s::jsonb, %s, %s)",
                (intent["request_id"], event["event_id"], canonical_json(event), record_hash, previous_hash),
            )
            return _receipt(event, record_hash, previous_hash)


def _receipt(event: dict, record_hash: str, previous_hash: str | None) -> dict:
    return {
        "request_id": event["intent"]["request_id"],
        "event_id": event["event_id"],
        "result": "DENY",
        "reason_code": event["reason_code"],
        "evidence_hash": record_hash,
        "previous_hash": previous_hash,
        "execution_invoked": False,
    }
