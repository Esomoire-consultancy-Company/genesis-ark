from __future__ import annotations

import hashlib
import json
from datetime import timezone


def test_edge_evidence_chain_covers_event_identity(enrolled_engine):
    events = enrolled_engine.list_events("node-001")
    assert len(events) == 1
    event = events[0]
    canonical = {
        "event_id": event.event_id,
        "node_id": event.node_id,
        "event_type": event.event_type,
        "actor_id": event.actor_id,
        "payload": event.payload,
        "occurred_at": event.occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "previous_event_hash": event.previous_event_hash,
    }
    expected = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert event.evidence_hash == expected
