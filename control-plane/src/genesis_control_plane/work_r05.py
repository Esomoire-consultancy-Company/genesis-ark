"""GWIEP R0.5: subject opt-in evidence and transactional staging outbox.

Offline source-and-tests only. No network handler, credential issuer, real
DigitalMe login, Docker operation, or automatic ChatGPT ingestion is provided.
Authoritative intake is the SQLite outbox; River JSONL is a verified projection.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.work_capture import accept_packet, verify_capture_envelope
from genesis_control_plane.work_consent import WardenConsentStore, _identifier
from genesis_control_plane.work_gateway import AdmissionDenied, WorkIntakeWarden
from genesis_control_plane.work_identity import DigitalMeAccessVerifier, IdentityContext
from genesis_control_plane.work_evidence import validate_payload

_PURPOSE = "work_evidence_capture"
_ALLOWED = frozenset({"work.input", "work.output", "work.tool", "work.revision"})


def _time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AdmissionDenied("R05_TIMEZONE_REQUIRED")
    return value.astimezone(timezone.utc).isoformat()


def _utc_now(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    _time(value)
    return value.astimezone(timezone.utc)


class WorkEvidenceStaging:
    """One SQLite-owned staging service; journal is downstream only.

    Production rollout must supply authenticated entrypoints, protected keys,
    a single authorized outbox consumer and independent evidence checkpoints.
    """

    def __init__(
        self, *, db_path: Path, river_path: Path,
        verifier: DigitalMeAccessVerifier,
        warden_store: WardenConsentStore,
        source_key_resolver: Callable[[str, str], bytes | None],
    ):
        if db_path.resolve() == river_path.resolve():
            raise AdmissionDenied("R05_STORAGE_PATH_CONFLICT")
        self.db_path, self.river_path = db_path, river_path
        self.verifier, self.warden_store = verifier, warden_store
        self.source_key_resolver = source_key_resolver
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path, timeout=10) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("""CREATE TABLE IF NOT EXISTS subject_consent (
                tenant_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                source TEXT NOT NULL,
                work_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                active INTEGER NOT NULL,
                generation INTEGER NOT NULL,
                PRIMARY KEY(tenant_id,principal_id,source,work_id)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS consent_audit (
                receipt_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                source TEXT NOT NULL,
                work_id TEXT NOT NULL,
                action TEXT NOT NULL,
                generation INTEGER NOT NULL,
                token_id_hash TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS capture_outbox (
                tenant_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                source TEXT NOT NULL,
                work_id TEXT NOT NULL,
                capture_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                packet_json TEXT NOT NULL,
                consent_generation INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','projected','blocked')),
                river_event_id TEXT,
                river_hash TEXT,
                blocked_reason TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY(tenant_id,source,capture_id)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS staging_scope ON capture_outbox(tenant_id,principal_id,work_id)")

    def _identity(self, token: str, scope: str, now: datetime) -> IdentityContext:
        return self.verifier.verify(token, required_scope=scope, now=now)

    @staticmethod
    def _audit(db: sqlite3.Connection, actor: IdentityContext, *, work_id: str,
               action: str, generation: int, now: datetime) -> str:
        receipt_id = f"GWIEP-AUD-{uuid4().hex}"
        db.execute("""INSERT INTO consent_audit
           (receipt_id,tenant_id,principal_id,source,work_id,action,
            generation,token_id_hash,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (receipt_id, actor.tenant_id, actor.subject, actor.source, work_id,
             action, generation, sha256_hex(actor.token_id), _time(now)))
        return receipt_id

    def opt_in(self, *, access_token: str, work_id: str, expires_at: datetime,
               purpose: str = _PURPOSE, now: datetime | None = None) -> dict:
        """Subject signs their own opt-in via externally verified access token.

        Proof is the validated subject/issuer/token ID + append-only audit row.
        This is a technical receipt, NOT a substitute for legal consent notice.
        """
        now = _utc_now(now)
        actor = self._identity(access_token, "work:consent", now)
        work_id = _identifier(work_id)
        if purpose != _PURPOSE:
            raise AdmissionDenied("R05_PURPOSE_DENIED")
        _time(expires_at)
        if expires_at <= now or expires_at > now + timedelta(days=30):
            raise AdmissionDenied("R05_CONSENT_DURATION_DENIED")
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("""SELECT generation FROM subject_consent WHERE
                tenant_id=? AND principal_id=? AND source=? AND work_id=?""",
                (actor.tenant_id, actor.subject, actor.source, work_id)).fetchone()
            generation = existing[0]+1 if existing else 1
            db.execute("""INSERT INTO subject_consent
                (tenant_id,principal_id,source,work_id,purpose,expires_at,active,generation)
                VALUES(?,?,?,?,?,?,1,?)
                ON CONFLICT(tenant_id,principal_id,source,work_id) DO UPDATE SET
                purpose=excluded.purpose, expires_at=excluded.expires_at,
                active=1,generation=excluded.generation""",
                (actor.tenant_id, actor.subject, actor.source, work_id,
                 purpose, _time(expires_at), generation))
            receipt = self._audit(db, actor, work_id=work_id, action="OPT_IN",
                                  generation=generation, now=now)
        return {"receipt_id": receipt, "status": "opted_in", "work_id": work_id,
                "generation": generation, "expires_at": _time(expires_at)}

    def withdraw(self, *, access_token: str, work_id: str,
                 now: datetime | None = None) -> dict:
        """Subject can withdraw without Warden admin intervention."""
        now = _utc_now(now)
        actor = self._identity(access_token, "work:consent", now)
        work_id = _identifier(work_id)
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT generation FROM subject_consent WHERE
                tenant_id=? AND principal_id=? AND source=? AND work_id=?""",
                (actor.tenant_id, actor.subject, actor.source, work_id)).fetchone()
            if row is None:
                raise AdmissionDenied("R05_CONSENT_NOT_FOUND")
            generation = row[0]+1
            db.execute("""UPDATE subject_consent SET active=0,generation=?
                WHERE tenant_id=? AND principal_id=? AND source=? AND work_id=?""",
                (generation, actor.tenant_id, actor.subject, actor.source, work_id))
            db.execute("""UPDATE capture_outbox SET status='blocked',
                blocked_reason='CONSENT_WITHDRAWN'
                WHERE tenant_id=? AND principal_id=? AND source=? AND work_id=? AND status='pending'""",
                (actor.tenant_id, actor.subject, actor.source, work_id))
            receipt = self._audit(db, actor, work_id=work_id,
                                  action="WITHDRAW", generation=generation, now=now)
        return {"receipt_id": receipt, "status": "withdrawn", "work_id": work_id,
                "generation": generation}

    @staticmethod
    def _require_consent(db: sqlite3.Connection, actor: IdentityContext,
                         work_id: str, now: datetime) -> int:
        row = db.execute("""SELECT purpose,expires_at,active,generation FROM subject_consent
            WHERE tenant_id=? AND principal_id=? AND source=? AND work_id=?""",
            (actor.tenant_id, actor.subject, actor.source, work_id)).fetchone()
        if row is None or not row[2] or row[0] != _PURPOSE:
            raise AdmissionDenied("R05_SUBJECT_CONSENT_REQUIRED")
        if datetime.fromisoformat(row[1]) <= now:
            raise AdmissionDenied("R05_SUBJECT_CONSENT_EXPIRED")
        return row[3]

    def admit(self, *, access_token: str, packet: dict,
              now: datetime | None = None) -> dict:
        """Transactional acceptance, no direct River mutation."""
        now = _utc_now(now)
        actor = self._identity(access_token, "work:capture", now)
        if not isinstance(packet, dict) or not isinstance(packet.get("payload"), dict):
            raise AdmissionDenied("R05_BAD_PACKET")
        p = packet["payload"]
        work_id = _identifier(p.get("work_id"))
        capture_id = _identifier(p.get("capture_id"))
        if p.get("tenant_id") != actor.tenant_id:
            raise AdmissionDenied("R05_TENANT_MISMATCH")
        source, grant = self.warden_store.resolve(actor, work_id=work_id, now=now)
        claims = {"tenant_id": actor.tenant_id, "principal_id": actor.subject,
                  "station_id": actor.station_id, "source": actor.source,
                  "session_id": actor.session_id}
        WorkIntakeWarden(source, grant).authorize(claims=claims, packet=packet, now=now)
        key = self.source_key_resolver(actor.tenant_id, actor.source)
        if not isinstance(key, bytes) or len(key) < 32:
            raise AdmissionDenied("R05_SOURCE_KEY_MISSING")
        try:
            verify_capture_envelope(packet, key=key, expected_station_id=actor.station_id,
                                    expected_principal_id=actor.subject,
                                    expected_source=actor.source, now=now)
            validate_payload(packet["kind"], p)
        except (ValueError, KeyError, TypeError) as exc:
            raise AdmissionDenied("R05_CAPTURE_INVALID") from exc
        # Stronger than only capture_id: retry can refresh issued_at/signature.
        fp = sha256_hex(canonical_json({
            "kind": packet["kind"], "payload": p,
            "station_id": packet["station_id"], "principal_id": packet["principal_id"],
            "session_id": packet["session_id"], "source": packet["source"],
            "correlation_id": packet["correlation_id"],
        }))
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            generation = self._require_consent(db, actor, work_id, now)
            row = db.execute("""SELECT fingerprint,status,consent_generation FROM capture_outbox
                WHERE tenant_id=? AND source=? AND capture_id=?""",
                (actor.tenant_id, actor.source, capture_id)).fetchone()
            if row:
                if row[0] != fp:
                    raise AdmissionDenied("R05_CAPTURE_ID_CONFLICT")
                # A duplicate never re-opens blocked evidence or widens scope.
                return {"status": row[1], "duplicate": True, "capture_id": capture_id}
            db.execute("""INSERT INTO capture_outbox
                (tenant_id,principal_id,source,work_id,capture_id,fingerprint,
                 packet_json,consent_generation,status,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (actor.tenant_id, actor.subject, actor.source, work_id, capture_id,
                 fp, canonical_json(packet), generation, "pending", _time(now)))
        return {"status": "pending", "duplicate": False, "capture_id": capture_id}

    def drain(self, *, now: datetime | None = None, limit: int = 25) -> dict:
        """Local trusted consumer: lock outbox, project, ack; retry is idempotent.

        The only writer of River work-capture events must be this consumer.
        """
        now = _utc_now(now)
        if not 1 <= limit <= 100:
            raise AdmissionDenied("R05_DRAIN_LIMIT_INVALID")
        projected, blocked = 0, 0
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("""SELECT tenant_id,principal_id,source,work_id,capture_id,
                        packet_json,consent_generation FROM capture_outbox
                        WHERE status='pending' ORDER BY created_at,capture_id LIMIT ?""",
                        (limit,)).fetchall()
            journal = EvidenceJournal(self.river_path)
            if not journal.verify_chain():
                raise AdmissionDenied("R05_RIVER_CHAIN_INVALID")
            for tenant, principal, source, work, capture, blob, generation in rows:
                consent = db.execute("""SELECT active,expires_at,generation
                    FROM subject_consent WHERE tenant_id=? AND principal_id=? AND
                    source=? AND work_id=?""",
                    (tenant, principal, source, work)).fetchone()
                if (consent is None or not consent[0] or
                    datetime.fromisoformat(consent[1]) <= now or
                    consent[2] != generation):
                    db.execute("""UPDATE capture_outbox SET status='blocked',
                        blocked_reason='CONSENT_NOT_ACTIVE'
                        WHERE tenant_id=? AND source=? AND capture_id=?""",
                        (tenant, source, capture))
                    blocked += 1
                    continue
                packet = json.loads(blob)
                # Lookup-only actor reconstructed from previously validated
                # admission; this does not grant new authority.
                actor = IdentityContext("", principal, tenant, packet["station_id"],
                                        source, packet["session_id"], "", frozenset({"work:capture"}), 0)
                try:
                    registered, grant = self.warden_store.resolve(actor, work_id=work, now=now)
                    WorkIntakeWarden(registered, grant).authorize(
                        claims={"tenant_id": tenant, "principal_id": principal,
                                "station_id": packet["station_id"], "source": source,
                                "session_id": packet["session_id"]},
                        packet=packet, now=now)
                    secret = self.source_key_resolver(tenant, source)
                    if not isinstance(secret, bytes) or len(secret) < 32:
                        raise AdmissionDenied("R05_SOURCE_KEY_MISSING")
                    # The packet was accepted earlier; after queuing a long time
                    # the original 5-minute signature freshness has expired.
                    # Verify the original MAC with its original issued_at time,
                    # but do not permit a new capture with a stale timestamp.
                    timestamp = datetime.fromisoformat(packet["issued_at"])
                    verify_capture_envelope(packet, key=secret,
                        expected_station_id=packet["station_id"],
                        expected_principal_id=principal,
                        expected_source=source, now=timestamp)
                except (ValueError, KeyError, TypeError) as exc:
                    db.execute("""UPDATE capture_outbox SET status='blocked',
                         blocked_reason='POLICY_OR_SIGNATURE_INVALID'
                         WHERE tenant_id=? AND source=? AND capture_id=?""",
                         (tenant, source, capture))
                    blocked += 1
                    continue
                # Project only metadata. If the process dies here before ack,
                # find the matching capture in the journal on retry.
                from genesis_control_plane.work_evidence import append_work_event
                existing = []
                for entry in journal._records():
                    ev = entry.get("event", {})
                    p = ev.get("payload", {})
                    if (isinstance(p, dict) and p.get("tenant_id") == tenant and
                        ev.get("source") == source and p.get("capture_id") == capture):
                        existing.append(entry)
                if len(existing) > 1:
                    raise AdmissionDenied("R05_RIVER_DUPLICATE_CAPTURE")
                if existing:
                    record = existing[0]
                    ev = record["event"]
                    if (ev.get("event_type") != packet["kind"] or
                        ev.get("payload") != packet["payload"] or
                        ev.get("principal_id") != principal or
                        ev.get("session_id") != packet["session_id"] or
                        ev.get("correlation_id") != packet["correlation_id"]):
                        raise AdmissionDenied("R05_RIVER_CAPTURE_CONFLICT")
                    event_id, record_hash = ev["event_id"], record["record_hash"]
                else:
                    receipt = append_work_event(
                        journal, kind=packet["kind"], payload=packet["payload"],
                        station_id=packet["station_id"], principal_id=principal,
                        session_id=packet["session_id"],
                        correlation_id=packet["correlation_id"], source=source,
                        classification="private",
                    )
                    event_id, record_hash = receipt.event_id, receipt.record_hash
                db.execute("""UPDATE capture_outbox SET status='projected',
                    river_event_id=?,river_hash=?
                    WHERE tenant_id=? AND source=? AND capture_id=?""",
                    (event_id, record_hash, tenant, source, capture))
                projected += 1
        return {"projected": projected, "blocked": blocked}

    def private_progress(self, *, access_token: str, work_id: str,
                         now: datetime | None = None) -> dict:
        """Read counters using independent token scope; no cross-tenant rows."""
        now = _utc_now(now)
        actor = self._identity(access_token, "work:read", now)
        work_id = _identifier(work_id)
        with sqlite3.connect(self.db_path, timeout=10) as db:
            rows = db.execute("""SELECT packet_json,status FROM capture_outbox
                WHERE tenant_id=? AND principal_id=? AND work_id=?""",
                (actor.tenant_id, actor.subject, work_id)).fetchall()
        if any(state == "projected" for _, state in rows):
            # Never advertise projected evidence as trustworthy if the
            # associated River receipt or hash chain is unavailable.
            check = self.reconcile()
            if check["projected_mismatches"]:
                raise AdmissionDenied("R05_PROJECTED_RECEIPT_INVALID")
        counts, projected_kinds = Counter(), Counter()
        channels, media, assets = Counter(), Counter(), Counter()
        for raw, state in rows:
            event = json.loads(raw)
            counts[state] += 1
            counts["submitted_" + event["kind"]] += 1
            # Submission is not evidence of RiverOS projection. Withdrawn
            # or failed packets are never represented as recorded inputs.
            if state != "projected":
                continue
            projected_kinds[event["kind"]] += 1
            payload = event["payload"]
            if event["kind"] == "work.input":
                channels[payload["channel"]] += 1
                media.update(set(payload["modalities"]))
                assets.update(a["modality"] for a in payload.get("attachments", []))
        return {
            "work_id": work_id, "tenant_id": actor.tenant_id,
            "principal_id": actor.subject, "accepted": len(rows),
            "pending": counts["pending"], "projected": counts["projected"],
            "blocked": counts["blocked"],
            "submitted_input_messages": counts["submitted_work.input"],
            "input_messages": projected_kinds["work.input"],
            "assistant_outputs": projected_kinds["work.output"],
            "tool_invocations": projected_kinds["work.tool"],
            "revisions": projected_kinds["work.revision"],
            "channels": dict(channels), "modalities": dict(media),
            "attachments": dict(assets), "source": "staging_outbox",
            "verified_execution_count": None, "finalized_count": None,
        }

    def reconcile(self) -> dict:
        """Trusted operator-only local consistency check (not a public route)."""
        journal = EvidenceJournal(self.river_path)
        if not journal.verify_chain():
            raise AdmissionDenied("R05_RIVER_CHAIN_INVALID")
        records = journal._records()
        index = {e["event"]["event_id"]: e for e in records}
        with sqlite3.connect(self.db_path, timeout=10) as db:
            rows = db.execute("""SELECT tenant_id,source,capture_id,status,
                river_event_id,river_hash FROM capture_outbox""").fetchall()
        mismatches = []
        for tenant, source, capture, status, event_id, record_hash in rows:
            if status == "projected":
                record = index.get(event_id)
                if (record is None or record["record_hash"] != record_hash or
                    record["event"].get("payload", {}).get("capture_id") != capture or
                    record["event"].get("payload", {}).get("tenant_id") != tenant or
                    record["event"].get("source") != source):
                    mismatches.append(capture)
        # On crashes between journal append and SQLite ack, a pending record
        # can have a projection without an indexed acknowledgement.
        projected = {(tenant, source, capture) for tenant, source, capture,
                     status, _, _ in rows if status == "projected"}
        orphaned = []
        for record in records:
            ev = record["event"]
            p = ev.get("payload", {})
            if isinstance(p, dict) and p.get("capture_id") and p.get("tenant_id"):
                key = (p["tenant_id"], ev.get("source"), p["capture_id"])
                if key not in projected:
                    orphaned.append(ev["event_id"])
        return {
            "outbox_rows": len(rows), "river_records": len(records),
            "projected_mismatches": mismatches, "unacknowledged_projections": orphaned,
            "consistent": not mismatches and not orphaned,
        }
