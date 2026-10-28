"""Verify the full local evidence spool before preparing a River witness request.

This verifier produces an *unwitnessed* digest summary. The output is not a
RiverOS receipt or independent attestation; a separate custodian must anchor
the digest outside the gateway database and verify it on later audits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from genesis_gateway.ledger import hash_record

MAX_ROWS = 100_000


class EvidenceIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class SpoolRow:
    seq: int
    request_id: str
    event_id: str
    event: Mapping[str, Any]
    previous_hash: str | None
    record_hash: str


def verify_rows(rows: Iterable[SpoolRow], *, expected_head: str | None = None) -> dict:
    """Validate genesis-to-head continuity; never silently verify a truncated set."""
    previous: str | None = None
    count = 0
    request_ids: set[str] = set()
    event_ids: set[str] = set()
    for row in rows:
        count += 1
        if count > MAX_ROWS:
            raise EvidenceIntegrityError("EXPORT_LIMIT_REACHED")
        if row.seq != count:
            raise EvidenceIntegrityError("MISSING_OR_REORDERED_SEQUENCE")
        if row.previous_hash != previous:
            raise EvidenceIntegrityError("BROKEN_HASH_LINK")
        event = row.event
        if (not isinstance(event, Mapping)
            or event.get("event_id") != row.event_id
            or not isinstance(event.get("intent"), Mapping)
            or event["intent"].get("request_id") != row.request_id):
            raise EvidenceIntegrityError("INCONSISTENT_EVENT_METADATA")
        if (event.get("schema_version") != "genesis-gateway-evidence.r0.1"
            or event.get("event_type") != "warden.decision.denied"
            or event.get("result") != "DENY"
            or event.get("execution_invoked") is not False
            or not isinstance(event.get("issuer_id"), str)):
            raise EvidenceIntegrityError("UNEXPECTED_EVIDENCE_TYPE")
        if row.request_id in request_ids or row.event_id in event_ids:
            raise EvidenceIntegrityError("DUPLICATE_EVIDENCE_ID")
        request_ids.add(row.request_id)
        event_ids.add(row.event_id)
        if row.record_hash != hash_record(dict(event), row.previous_hash):
            raise EvidenceIntegrityError("EVENT_DIGEST_MISMATCH")
        previous = row.record_hash

    if count == 0:
        raise EvidenceIntegrityError("EMPTY_SPOOL")
    if expected_head is not None and expected_head != previous:
        raise EvidenceIntegrityError("EXTERNAL_ANCHOR_MISMATCH")
    return {
        "schema": "genesis-gateway-spool-check.r0.2",
        "verification": "local-spool-verified",
        "first_seq": 1,
        "last_seq": count,
        "event_count": count,
        "head_hash": previous,
        "external_witnessed": False,
        "riveros_receipt": None,
    }


def verify_database(dsn: str, *, expected_head: str | None = None) -> dict:
    """Read under an independent SELECT-only role; never grant to the web API."""
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise EvidenceIntegrityError("READONLY_DATABASE_DSN_REQUIRED")
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            # One consistent snapshot: a new insertion between count and fetch
            # must not corrupt the meaning of "full history".
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cur.execute("""
                SELECT
                    (SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                       FROM pg_roles WHERE rolname = current_user),
                    has_schema_privilege(current_user, 'public', 'CREATE'),
                    has_table_privilege(current_user, 'public.gateway_evidence', 'SELECT'),
                    has_table_privilege(current_user, 'public.gateway_evidence', 'INSERT'),
                    has_table_privilege(current_user, 'public.gateway_evidence', 'UPDATE'),
                    has_table_privilege(current_user, 'public.gateway_evidence', 'DELETE'),
                    has_table_privilege(current_user, 'public.gateway_evidence', 'TRUNCATE')
            """)
            privileged, create_schema, can_select, can_insert, can_update, can_delete, can_truncate = cur.fetchone()
            if not can_select or any((privileged, create_schema, can_insert, can_update, can_delete, can_truncate)):
                raise EvidenceIntegrityError("AUDIT_ROLE_NOT_READONLY")
            cur.execute("SELECT count(*) FROM public.gateway_evidence")
            total = cur.fetchone()[0]
            if total == 0 or total > MAX_ROWS:
                raise EvidenceIntegrityError("EMPTY_OR_OVERSIZE_SPOOL")
            cur.execute(
                "SELECT seq, request_id::text, event_id::text, event, "
                "previous_hash, record_hash FROM public.gateway_evidence ORDER BY seq ASC"
            )
            rows = (SpoolRow(*entry) for entry in cur.fetchall())
            return verify_rows(rows, expected_head=expected_head)


def main() -> None:
    """Print only digest metadata; never database connection strings or raw events."""
    import json
    dsn = os.getenv("GENESIS_WITNESS_READONLY_DATABASE_URL", "")
    anchor = os.getenv("GENESIS_WITNESS_EXPECTED_HEAD") or None
    print(json.dumps(verify_database(dsn, expected_head=anchor), sort_keys=True))


if __name__ == "__main__":
    main()
