from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from .models import ControlTowerEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def build_event(
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    actor_id: str,
    payload: dict[str, Any],
    previous_event_hash: str | None,
    occurred_at: datetime,
) -> ControlTowerEvent:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("Control Tower event timestamps must be timezone-aware")
    occurred_at = occurred_at.astimezone(timezone.utc)
    event_id = new_id("CONTROL-EVENT")
    canonical = {
        "event_id": event_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload,
        "occurred_at": occurred_at.isoformat(),
        "previous_event_hash": previous_event_hash,
    }
    evidence_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return ControlTowerEvent(evidence_hash=evidence_hash, **canonical)


def source_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False).encode("utf-8")
    ).hexdigest()
