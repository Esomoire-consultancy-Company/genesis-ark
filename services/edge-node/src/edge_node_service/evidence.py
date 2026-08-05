from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

from .models import EdgeEvidenceEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def build_evidence_event(
    *,
    node_id: str,
    event_type: str,
    actor_id: str,
    payload: dict[str, object],
    occurred_at: datetime,
    previous_event_hash: str | None,
) -> EdgeEvidenceEvent:
    event_id = f"edgeevt-{uuid.uuid4().hex}"
    canonical = {
        "event_id": event_id,
        "node_id": node_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload,
        "occurred_at": occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "previous_event_hash": previous_event_hash,
    }
    evidence_hash = hashlib.sha256(_canonical_json(canonical)).hexdigest()
    return EdgeEvidenceEvent(
        **canonical,
        evidence_hash=evidence_hash,
    )
