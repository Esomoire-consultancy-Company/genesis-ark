from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from .models import RuntimeEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def build_runtime_event(
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
    previous_event_hash: str | None,
    box_id: str | None = None,
    occurred_at: datetime | None = None,
) -> RuntimeEvent:
    timestamp = occurred_at or utcnow()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("runtime event timestamps must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    event_id = new_id("RUNTIME-EVENT")
    canonical = {
        "event_id": event_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "box_id": box_id,
        "event_type": event_type,
        "payload": payload,
        "occurred_at": timestamp.isoformat(),
        "previous_event_hash": previous_event_hash,
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    evidence_hash = hashlib.sha256(encoded).hexdigest()
    return RuntimeEvent(
        evidence_hash=evidence_hash,
        **canonical,
    )
