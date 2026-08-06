from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .errors import StateConflictError
from .models import CapabilityAuthorization, ControlTowerEvent, FleetAsset, FleetCommand, Incident
from .postgres_base import _decode_fields, _decode_json

class PostgresEventOperations:
    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent:
        with self._connection() as connection:
            try:
                self._execute(
                    connection,
                    """
                    insert into genesis_control_tower.events (
                      event_id, aggregate_type, aggregate_id, subject_id,
                      event_type, actor_id, payload, occurred_at,
                      previous_event_hash, evidence_hash, published_at
                    ) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    """,
                    (
                        event.event_id,
                        event.aggregate_type,
                        event.aggregate_id,
                        event.subject_id,
                        event.event_type,
                        event.actor_id,
                        json.dumps(event.payload),
                        event.occurred_at,
                        event.previous_event_hash,
                        event.evidence_hash,
                        event.published_at,
                    ),
                )
            except Exception as exc:
                raise StateConflictError(
                    "Control Tower event could not be appended",
                    reason_codes=["EVIDENCE_APPEND_CONFLICT"],
                ) from exc
        return event

    def latest_event(self, aggregate_type: str, aggregate_id: str) -> ControlTowerEvent | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select event_id, aggregate_type, aggregate_id, subject_id,
                       event_type, actor_id, payload, occurred_at,
                       previous_event_hash, evidence_hash, published_at
                from genesis_control_tower.events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at desc, event_id desc limit 1
                """,
                (aggregate_type, aggregate_id),
            )
        decoded = _decode_fields(row, "payload")
        return ControlTowerEvent.model_validate(decoded) if decoded else None

    def list_events_for_subject(self, subject_id: str) -> list[ControlTowerEvent]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select event_id, aggregate_type, aggregate_id, subject_id,
                       event_type, actor_id, payload, occurred_at,
                       previous_event_hash, evidence_hash, published_at
                from genesis_control_tower.events
                where subject_id = %s order by occurred_at, event_id
                """,
                (subject_id,),
            )
        return [ControlTowerEvent.model_validate(_decode_fields(row, "payload")) for row in rows]
