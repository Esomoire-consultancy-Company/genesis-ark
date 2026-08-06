from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .capabilities import CapabilityGrant
from .errors import AuthorizationError, StateConflictError
from .models import EdgeEvidenceEvent, SpoolEvent

_EVENT_COLUMNS = """
event_id, node_id, event_type, actor_id, payload,
occurred_at, previous_event_hash, evidence_hash
"""


def _event(row: Any) -> EdgeEvidenceEvent | None:
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"]) if isinstance(data["payload"], str) else data["payload"]
    return EdgeEvidenceEvent.model_validate(data)


class PostgresEvidenceMixin:
    def ingest_spool_event(self, node_id: str, event: SpoolEvent, at: datetime) -> bool:
        with self._connection() as connection:
            inserted = self._one(
                connection,
                """
                insert into genesis_edge.edge_spool_events (
                  event_id, node_id, sequence, event_type, actor_id,
                  occurred_at, payload, previous_local_hash, local_hash, ingested_at
                ) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                on conflict (event_id) do nothing returning event_id
                """,
                (
                    event.event_id,
                    node_id,
                    event.sequence,
                    event.event_type,
                    event.actor_id,
                    event.occurred_at,
                    json.dumps(event.payload),
                    event.previous_local_hash,
                    event.local_hash,
                    at,
                ),
            )
            if inserted is not None:
                return True
            existing = self._one(
                connection,
                "select node_id, local_hash from genesis_edge.edge_spool_events where event_id = %s",
                (event.event_id,),
            )
            if existing is None or existing["node_id"] != node_id or existing["local_hash"] != event.local_hash:
                raise StateConflictError(
                    "Spool event ID conflicts with previously ingested content",
                    reason_codes=["SPOOL_EVENT_ID_CONFLICT"],
                )
            return False

    def append_event(self, event: EdgeEvidenceEvent) -> EdgeEvidenceEvent:
        with self._connection() as connection:
            latest = self._one(
                connection,
                "select evidence_hash from genesis_edge.edge_evidence_events where node_id = %s order by occurred_at desc, event_id desc limit 1",
                (event.node_id,),
            )
            expected = latest["evidence_hash"] if latest else None
            if event.previous_event_hash != expected:
                raise StateConflictError(
                    "Edge evidence event does not continue the node chain",
                    reason_codes=["EVIDENCE_CHAIN_CONFLICT"],
                )
            self._run(
                connection,
                """
                insert into genesis_edge.edge_evidence_events (
                  event_id, node_id, event_type, actor_id, payload,
                  occurred_at, previous_event_hash, evidence_hash
                ) values (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                """,
                (
                    event.event_id,
                    event.node_id,
                    event.event_type,
                    event.actor_id,
                    json.dumps(event.payload),
                    event.occurred_at,
                    event.previous_event_hash,
                    event.evidence_hash,
                ),
            )
        return event

    def latest_event(self, node_id: str) -> EdgeEvidenceEvent | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                f"select {_EVENT_COLUMNS} from genesis_edge.edge_evidence_events where node_id = %s order by occurred_at desc, event_id desc limit 1",
                (node_id,),
            )
        return _event(row)

    def list_events(self, node_id: str) -> list[EdgeEvidenceEvent]:
        with self._connection() as connection:
            rows = self._all(
                connection,
                f"select {_EVENT_COLUMNS} from genesis_edge.edge_evidence_events where node_id = %s order by occurred_at, event_id",
                (node_id,),
            )
        return [item for row in rows if (item := _event(row)) is not None]

    def verify(
        self,
        *,
        capability_id: str,
        subject_id: str,
        resource_id: str,
        allowed_action: str,
        at: datetime,
    ) -> CapabilityGrant:
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select capability_id, subject_id, resource_id, allowed_action, expires_at
                from public.active_capability_grants
                where capability_id = %s and subject_id = %s and resource_id = %s
                  and allowed_action = %s and expires_at > %s
                """,
                (capability_id, subject_id, resource_id, allowed_action, at),
            )
        if row is None:
            raise AuthorizationError(
                "Capability is missing, revoked, expired or does not match this command",
                reason_codes=["CAPABILITY_INACTIVE"],
            )
        return CapabilityGrant(
            capability_id=row["capability_id"],
            subject_id=row["subject_id"],
            resource_id=row["resource_id"],
            allowed_action=row["allowed_action"],
            expires_at=row["expires_at"],
        )
