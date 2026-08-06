from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from .models import EvidenceEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def build_event(
    *,
    browser_session_id: str,
    box_id: str,
    event_type: str,
    actor_id: str,
    action_reference: str,
    payload: dict[str, Any],
    previous_event_hash: str | None,
    timestamp: datetime | None = None,
) -> EvidenceEvent:
    occurred_at = timestamp or utcnow()
    canonical = {
        "browser_session_id": browser_session_id,
        "box_id": box_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "action_reference": action_reference,
        "timestamp": occurred_at.isoformat(),
        "payload": payload,
        "previous_event_hash": previous_event_hash,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return EvidenceEvent(
        event_id=new_id("BROWSER-EVENT"),
        evidence_hash=digest,
        **canonical,
    )
