from __future__ import annotations

from datetime import datetime
import hashlib
import json

import pytest

from runtime_service.evidence import build_runtime_event


def test_runtime_event_hash_covers_event_identity() -> None:
    event = build_runtime_event(
        aggregate_type="SESSION",
        aggregate_id="SESSION-001",
        event_type="RUNTIME_SESSION_STARTED",
        payload={"value": 1},
        previous_event_hash=None,
    )
    canonical = {
        "event_id": event.event_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "box_id": event.box_id,
        "event_type": event.event_type,
        "payload": event.payload,
        "occurred_at": event.occurred_at.isoformat(),
        "previous_event_hash": event.previous_event_hash,
    }
    expected = hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    assert event.evidence_hash == expected


def test_runtime_event_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_runtime_event(
            aggregate_type="SESSION",
            aggregate_id="SESSION-001",
            event_type="RUNTIME_SESSION_STARTED",
            payload={},
            previous_event_hash=None,
            occurred_at=datetime(2026, 8, 6, 0, 0),
        )
