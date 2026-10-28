"""Local, authenticated intake for source-observed GWIEP metadata packets.

Library-only R0.2 prototype: no HTTP listener, no automatic ChatGPT hooks,
no production connection. Only approved, trusted source adapters should have
signing keys. An adapter's observation is not independent Warden verification.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from genesis_control_plane.canonical import canonical_json
from genesis_control_plane.evidence import EvidenceJournal, EvidenceReceipt
from genesis_control_plane.work_evidence import append_work_event, validate_payload

_ALLOWED = frozenset({"work.input", "work.output", "work.tool", "work.revision"})
_FIELDS = frozenset({"kind", "payload", "station_id", "principal_id", "session_id", "correlation_id", "source", "issued_at"})


def _mac(payload: Mapping[str, Any], key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("WORK_CAPTURE_SIGNING_KEY_REQUIRED")
    return hmac.new(key, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def sign_packet(packet: Mapping[str, Any], key: bytes) -> dict:
    """Trusted source adapter signs a fresh envelope; no payload content included."""
    if set(packet) != _FIELDS:
        raise ValueError("WORK_CAPTURE_INVALID_ENVELOPE")
    return {**packet, "signature": _mac(packet, key)}


def verify_capture_envelope(
    packet: Mapping[str, Any], *, key: bytes,
    expected_station_id: str, expected_principal_id: str, expected_source: str,
    now: datetime | None = None,
) -> None:
    """Validate HMAC signature, source, message schema, and freshness, without writes."""
    if not isinstance(packet, dict) or set(packet) != (_FIELDS | {"signature"}):
        raise ValueError("WORK_CAPTURE_INVALID_ENVELOPE")
    signature = packet.get("signature")
    if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{64}", signature):
        raise ValueError("WORK_CAPTURE_BAD_SIGNATURE")
    unsigned = {k: packet[k] for k in _FIELDS}
    if not hmac.compare_digest(_mac(unsigned, key), signature):
        raise ValueError("WORK_CAPTURE_BAD_SIGNATURE")
    if (packet["station_id"] != expected_station_id or
        packet["principal_id"] != expected_principal_id or
        packet["source"] != expected_source):
        raise ValueError("WORK_CAPTURE_WRONG_AUTHORITY_SCOPE")
    if packet["kind"] not in _ALLOWED:
        raise ValueError("WORK_CAPTURE_REQUIRES_WARDEN")
    if not isinstance(packet["payload"], dict):
        raise ValueError("WORK_CAPTURE_INVALID_PAYLOAD")
    validate_payload(packet["kind"], packet["payload"])
    capture_id = packet["payload"].get("capture_id")
    if not isinstance(capture_id, str) or not 0 < len(capture_id) <= 256:
        raise ValueError("WORK_CAPTURE_ID_REQUIRED")
    for key_name in ("session_id", "correlation_id"):
        value = packet.get(key_name)
        if not isinstance(value, str) or not 0 < len(value) <= 256:
            raise ValueError("WORK_CAPTURE_INVALID_ENVELOPE")
    try:
        time = datetime.fromisoformat(packet["issued_at"])
        if time.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("WORK_CAPTURE_BAD_TIMESTAMP") from exc
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("WORK_CAPTURE_TIMEZONE_REQUIRED")
    if abs((now - time).total_seconds()) > 300:
        raise ValueError("WORK_CAPTURE_EXPIRED")


def accept_packet(
    journal: EvidenceJournal, packet: Mapping[str, Any], *, key: bytes,
    expected_station_id: str, expected_principal_id: str, expected_source: str,
    now: datetime | None = None,
) -> EvidenceReceipt:
    """Validate signed packet before deduplication, then append to local River."""
    verify_capture_envelope(
        packet, key=key, expected_station_id=expected_station_id,
        expected_principal_id=expected_principal_id, expected_source=expected_source, now=now,
    )
    capture_id = packet["payload"]["capture_id"]
    if not journal.verify_chain():
        raise ValueError("EVIDENCE_CHAIN_INVALID")
    for i, record in enumerate(journal._records(), start=1):
        event = record["event"]
        existing_payload = event.get("payload", {})
        if (event.get("source") == packet["source"] and
            isinstance(existing_payload, dict) and
            existing_payload.get("capture_id") == capture_id):
            if (event["event_type"] != packet["kind"] or
                existing_payload != packet["payload"] or
                event["principal_id"] != packet["principal_id"] or
                event["station_id"] != packet["station_id"] or
                event["session_id"] != packet["session_id"] or
                event["correlation_id"] != packet["correlation_id"]):
                raise ValueError("WORK_CAPTURE_ID_CONFLICT")
            return EvidenceReceipt(event["event_id"], record["record_hash"],
                                   record["previous_hash"], i)
    return append_work_event(
        journal, kind=packet["kind"], payload=packet["payload"],
        station_id=packet["station_id"], principal_id=packet["principal_id"],
        session_id=packet["session_id"], correlation_id=packet["correlation_id"],
        source=packet["source"], classification="private",
    )
