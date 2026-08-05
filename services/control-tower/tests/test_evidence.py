from __future__ import annotations

from datetime import datetime, timezone

from control_tower_service.evidence import build_event


def test_control_tower_evidence_hash_covers_event_identity():
    at = datetime(2026, 8, 6, tzinfo=timezone.utc)
    first = build_event(
        aggregate_type="FLEET",
        aggregate_id="GENESIS-FLEET",
        event_type="CONTROL_FLEET_REFRESHED",
        actor_id="ACTOR-OPS",
        payload={"count": 1},
        previous_event_hash=None,
        occurred_at=at,
    )
    second = build_event(
        aggregate_type="FLEET",
        aggregate_id="GENESIS-FLEET",
        event_type="CONTROL_FLEET_REFRESHED",
        actor_id="ACTOR-OPS",
        payload={"count": 1},
        previous_event_hash=None,
        occurred_at=at,
    )
    assert first.event_id != second.event_id
    assert first.evidence_hash != second.evidence_hash
