"""GWIEP R0.3: local Genesis Gateway admission and Warden consent gate.

This library is a NON-DEPLOYED Alpha integration contract. Identity sessions are
HMAC-signed by a trusted local issuer; they are NOT production DigitalMe SSO.
No API listener, ChatGPT surveillance, or Docker execution is introduced.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.evidence import EvidenceJournal, EvidenceReceipt
from genesis_control_plane.work_capture import accept_packet
from genesis_control_plane.work_evidence import validate_payload

_AUDIENCE = "genesis-work-intake-alpha"
_ALLOWED_KINDS = frozenset({"work.input", "work.output", "work.tool", "work.revision"})
_SESSION_FIELDS = frozenset({
    "tenant_id", "principal_id", "station_id", "source", "session_id",
    "audience", "issued_at", "expires_at",
})


class AdmissionDenied(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class RegisteredSource:
    tenant_id: str
    principal_id: str
    station_id: str
    source: str
    channels: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class ConsentGrant:
    consent_id: str
    tenant_id: str
    principal_id: str
    station_id: str
    source: str
    work_id: str
    valid_until: datetime
    allowed_kinds: frozenset[str] = _ALLOWED_KINDS
    active: bool = True


@dataclass(frozen=True)
class AdmissionReceipt:
    event_id: str
    record_hash: str
    line_number: int
    policy_id: str
    consent_id: str
    duplicate: bool


def _check_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise AdmissionDenied("GATEWAY_SIGNING_KEY_REQUIRED")


def _time(value: object, reason: str) -> datetime:
    if not isinstance(value, str):
        raise AdmissionDenied(reason)
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("naive")
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise AdmissionDenied(reason) from exc


def _check_id(value: object, reason: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise AdmissionDenied(reason)
    return value


def issue_local_test_session(claims: Mapping[str, str], key: bytes) -> dict:
    """Fixture/offline issuer only; no public endpoint may expose this method."""
    _check_key(key)
    if set(claims) != _SESSION_FIELDS:
        raise AdmissionDenied("GATEWAY_SESSION_SCHEMA")
    if claims["audience"] != _AUDIENCE:
        raise AdmissionDenied("GATEWAY_AUDIENCE_DENIED")
    for val in claims.values():
        _check_id(val, "GATEWAY_SESSION_SCHEMA")
    material = canonical_json(dict(claims))
    signature = hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"claims": dict(claims), "signature": signature}


def verify_local_session(token: object, key: bytes, *, now: datetime) -> dict[str, str]:
    """Validate issuer-signed claims, audience, bounded TTL and timestamp."""
    _check_key(key)
    if not isinstance(token, dict) or set(token) != {"claims", "signature"}:
        raise AdmissionDenied("GATEWAY_SESSION_MALFORMED")
    claims, signature = token["claims"], token["signature"]
    if not isinstance(claims, dict) or set(claims) != _SESSION_FIELDS:
        raise AdmissionDenied("GATEWAY_SESSION_SCHEMA")
    if any(not isinstance(x, str) or not x.strip() or len(x) > 256 for x in claims.values()):
        raise AdmissionDenied("GATEWAY_SESSION_SCHEMA")
    if not isinstance(signature, str) or len(signature) != 64:
        raise AdmissionDenied("GATEWAY_SESSION_SIGNATURE_INVALID")
    expected = hmac.new(key, canonical_json(claims).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AdmissionDenied("GATEWAY_SESSION_SIGNATURE_INVALID")
    if claims["audience"] != _AUDIENCE:
        raise AdmissionDenied("GATEWAY_AUDIENCE_DENIED")
    issued = _time(claims["issued_at"], "GATEWAY_SESSION_TIME_INVALID")
    expires = _time(claims["expires_at"], "GATEWAY_SESSION_TIME_INVALID")
    if now.tzinfo is None:
        raise AdmissionDenied("GATEWAY_CLOCK_INVALID")
    utc_now = now.astimezone(timezone.utc)
    if issued > utc_now + timedelta(seconds=60) or expires <= utc_now:
        raise AdmissionDenied("GATEWAY_SESSION_EXPIRED")
    if expires <= issued or expires - issued > timedelta(minutes=15):
        raise AdmissionDenied("GATEWAY_SESSION_DURATION_INVALID")
    return claims


class WorkIntakeWarden:
    """Separate policy from the existing Docker-mutation Warden capabilities.

    Registry/grant inputs MUST be obtained from a trusted administrative plane,
    never supplied from the same user packet that requests admission.
    """
    policy_id = "WARDEN-WORK-INTAKE-ALPHA-R0.3"

    def __init__(self, registered_source: RegisteredSource, grant: ConsentGrant):
        self.registered_source = registered_source
        self.grant = grant

    def authorize(self, *, claims: Mapping[str, str], packet: Mapping[str, Any], now: datetime) -> None:
        source, grant = self.registered_source, self.grant
        for field in ("tenant_id", "principal_id", "station_id", "source"):
            if claims[field] != getattr(source, field) or claims[field] != getattr(grant, field):
                raise AdmissionDenied("WARDEN_ACTOR_BINDING_DENIED")
        if not source.active:
            raise AdmissionDenied("WARDEN_SOURCE_REVOKED")
        if not grant.active:
            raise AdmissionDenied("WARDEN_CONSENT_REVOKED")
        if grant.valid_until.tzinfo is None or grant.valid_until <= now:
            raise AdmissionDenied("WARDEN_CONSENT_EXPIRED")
        if packet.get("kind") not in _ALLOWED_KINDS or packet["kind"] not in grant.allowed_kinds:
            raise AdmissionDenied("WARDEN_CAPABILITY_DENIED")
        payload = packet.get("payload")
        if not isinstance(payload, dict):
            raise AdmissionDenied("WARDEN_PAYLOAD_DENIED")
        if payload.get("work_id") != grant.work_id:
            raise AdmissionDenied("WARDEN_WORKSTREAM_DENIED")
        try:
            validate_payload(packet["kind"], payload)
        except (ValueError, TypeError) as exc:
            raise AdmissionDenied("WARDEN_EVENT_SCHEMA_DENIED") from exc
        if packet["kind"] == "work.input":
            if payload["channel"] not in source.channels:
                raise AdmissionDenied("WARDEN_SOURCE_CHANNEL_DENIED")
            # Unknown historic source must go through the consent-based import path.
            if payload["channel"] == "import_unknown":
                raise AdmissionDenied("WARDEN_SOURCE_CHANNEL_DENIED")
            if payload["provenance"] != "observed":
                raise AdmissionDenied("WARDEN_ORIGIN_UNVERIFIED")
        if packet.get("station_id") != claims["station_id"] or packet.get("source") != claims["source"]:
            raise AdmissionDenied("WARDEN_PACKET_BINDING_DENIED")
        if packet.get("principal_id") != claims["principal_id"] or packet.get("session_id") != claims["session_id"]:
            raise AdmissionDenied("WARDEN_PACKET_BINDING_DENIED")


class WorkIntakeGateway:
    """Single-writer-gateway admission with durable SQLite idempotency index.

    The River JSONL file must have no writers bypassing this gateway for work
    admission; cross-process locking covers cooperating gateways using the
    *same* sqlite file, but cannot lock independent raw journal writers.
    """

    def __init__(
        self, *, ledger_path: Path, journal_path: Path,
        identity_signing_key: bytes, source_signing_key: bytes,
        source: RegisteredSource, grant: ConsentGrant,
    ):
        _check_key(identity_signing_key)
        _check_key(source_signing_key)
        if hmac.compare_digest(identity_signing_key, source_signing_key):
            raise AdmissionDenied("GATEWAY_KEY_SEPARATION_REQUIRED")
        if ledger_path.resolve() == journal_path.resolve():
            raise AdmissionDenied("GATEWAY_STORAGE_PATH_CONFLICT")
        self.ledger_path, self.journal_path = ledger_path, journal_path
        self.identity_signing_key, self.source_signing_key = identity_signing_key, source_signing_key
        self.warden = WorkIntakeWarden(source, grant)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal = EvidenceJournal(journal_path)
        with sqlite3.connect(ledger_path, timeout=10) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS accepted_work (
                tenant_id TEXT NOT NULL,
                source TEXT NOT NULL,
                capture_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                work_id TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                consent_id TEXT NOT NULL,
                policy_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, source, capture_id)
            )""")

    @staticmethod
    def _fingerprint(packet: Mapping[str, Any]) -> str:
        # Ignore signature/issued_at to allow a timestamp-refreshed retry of
        # the identical capture without double-counting it.
        return sha256_hex(canonical_json({
            "kind": packet["kind"], "payload": packet["payload"],
            "station_id": packet["station_id"], "principal_id": packet["principal_id"],
            "session_id": packet["session_id"], "source": packet["source"],
            "correlation_id": packet["correlation_id"],
        }))

    def admit(self, *, session_token: dict, packet: dict, now: datetime | None = None) -> AdmissionReceipt:
        now = now or datetime.now(timezone.utc)
        claims = verify_local_session(session_token, self.identity_signing_key, now=now)
        self.warden.authorize(claims=claims, packet=packet, now=now)
        capture_id = _check_id(packet["payload"].get("capture_id"), "GATEWAY_CAPTURE_ID_REQUIRED")
        key = (claims["tenant_id"], claims["source"], capture_id)
        fingerprint = self._fingerprint(packet)
        # BEGIN IMMEDIATE prevents concurrent cooperating gateway processes
        # accepting the same capture_id simultaneously.
        with sqlite3.connect(self.ledger_path, timeout=10, isolation_level=None) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    """SELECT content_hash, event_id, record_hash, line_number
                       FROM accepted_work WHERE tenant_id=? AND source=? AND capture_id=?""",
                    key,
                ).fetchone()
                if row:
                    if row[0] != fingerprint:
                        raise AdmissionDenied("GATEWAY_CAPTURE_ID_CONFLICT")
                    self._verify_record(row[1], row[2])
                    conn.execute("COMMIT")
                    return AdmissionReceipt(row[1], row[2], row[3],
                                            self.warden.policy_id, self.warden.grant.consent_id, True)
                try:
                    river = accept_packet(
                        self.journal, packet, key=self.source_signing_key,
                        expected_station_id=claims["station_id"],
                        expected_principal_id=claims["principal_id"],
                        expected_source=claims["source"], now=now,
                    )
                except ValueError as exc:
                    raise AdmissionDenied("GATEWAY_SOURCE_PACKET_DENIED") from exc
                # If River succeeds but SQLite commit is interrupted, a
                # retry can recover from River's existing capture_id record.
                conn.execute(
                    """INSERT INTO accepted_work
                      (tenant_id, source, capture_id, content_hash, work_id, principal_id,
                       consent_id, policy_id, event_id, record_hash, line_number)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*key, fingerprint, packet["payload"]["work_id"], claims["principal_id"],
                     self.warden.grant.consent_id, self.warden.policy_id, river.event_id,
                     river.record_hash, river.line_number),
                )
                conn.execute("COMMIT")
                return AdmissionReceipt(river.event_id, river.record_hash, river.line_number,
                                        self.warden.policy_id, self.warden.grant.consent_id, False)
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def _verify_record(self, event_id: str, record_hash: str) -> None:
        if not self.journal.verify_chain():
            raise AdmissionDenied("GATEWAY_RIVER_CHAIN_INVALID")
        found = [r for r in self.journal._records() if r.get("event", {}).get("event_id") == event_id]
        if len(found) != 1 or found[0].get("record_hash") != record_hash:
            raise AdmissionDenied("GATEWAY_RIVER_RECEIPT_MISMATCH")

    def reconcile(self) -> dict[str, Any]:
        """Read-only consistency report; never calls an external system."""
        if not self.journal.verify_chain():
            raise AdmissionDenied("GATEWAY_RIVER_CHAIN_INVALID")
        records = self.journal._records()
        event_hashes = {r["event"]["event_id"]: r["record_hash"] for r in records}
        with sqlite3.connect(self.ledger_path, timeout=10) as conn:
            rows = conn.execute("SELECT tenant_id, source, capture_id, work_id, event_id, record_hash FROM accepted_work").fetchall()
        missing_receipts = []
        for tenant, source, capture, work, event, expected_hash in rows:
            if event_hashes.get(event) != expected_hash:
                missing_receipts.append({"tenant_id": tenant, "capture_id": capture, "work_id": work})
        recorded = {(source, capture, event) for _, source, capture, _, event, _ in rows}
        unindexed = []
        for r in records:
            e = r["event"]
            p = e.get("payload", {})
            if e.get("event_type") in _ALLOWED_KINDS and isinstance(p, dict) and p.get("capture_id"):
                if (e.get("source"), p["capture_id"], e["event_id"]) not in recorded:
                    unindexed.append({"event_id": e["event_id"], "work_id": p.get("work_id")})
        return {
            "indexed_acceptances": len(rows),
            "river_events": len(records),
            "missing_receipts": missing_receipts,
            "unindexed_river_captures": unindexed,
            "consistent": not missing_receipts and not unindexed,
            "journal_hash_chain_verified": True,
        }
