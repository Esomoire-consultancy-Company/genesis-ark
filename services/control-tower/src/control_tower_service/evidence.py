from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from .models import ControlTowerEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def build_event(
    *,
    aggregate_type: str,
    aggregate_id: str,
    subject_id: str,
    event_type: str,
    actor_id: str,
    payload: dict[str, Any],
    previous_event_hash: str | None,
    occurred_at: datetime | None = None,
) -> ControlTowerEvent:
    timestamp = occurred_at or utcnow()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Control Tower event timestamps must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    event_id = new_id("CT-EVENT")
    canonical = {
        "event_id": event_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "subject_id": subject_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload,
        "occurred_at": timestamp.isoformat(),
        "previous_event_hash": previous_event_hash,
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return ControlTowerEvent(
        evidence_hash=hashlib.sha256(encoded).hexdigest(),
        **canonical,
    )
