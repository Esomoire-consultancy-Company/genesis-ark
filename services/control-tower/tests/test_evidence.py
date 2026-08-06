from __future__ import annotations

from datetime import datetime, timezone

import pytest

from control_tower_service.evidence import build_event


def test_event_hash_covers_event_identity():
    first = build_event(
        aggregate_type="FLEET_ASSET",
        aggregate_id="NODE-BLR-001",
        subject_id="NODE-BLR-001",
        event_type="FLEET_ASSET_OBSERVED",
        actor_id="GENESIS-OPS-001",
        payload={"status": "HEALTHY"},
        previous_event_hash=None,
        occurred_at=datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc),
    )
    second = build_event(
        aggregate_type="FLEET_ASSET",
        aggregate_id="NODE-BLR-001",
        subject_id="NODE-BLR-001",
        event_type="FLEET_ASSET_OBSERVED",
        actor_id="GENESIS-OPS-001",
        payload={"status": "HEALTHY"},
        previous_event_hash=None,
        occurred_at=datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc),
    )
    assert first.event_id != second.event_id
    assert first.evidence_hash != second.evidence_hash


def test_event_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_event(
            aggregate_type="FLEET_ASSET",
            aggregate_id="NODE-BLR-001",
            subject_id="NODE-BLR-001",
            event_type="FLEET_ASSET_OBSERVED",
            actor_id="GENESIS-OPS-001",
            payload={},
            previous_event_hash=None,
            occurred_at=datetime(2026, 8, 6, 0, 0),
        )
