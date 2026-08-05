from __future__ import annotations

from datetime import datetime
import json
import secrets
from typing import Any

from .errors import AuthorizationError, NotFoundError, StateConflictError
from .models import CapabilityGrant, ControlTowerEvent, PublicationAckItem, PublicationLeaseStatus, PublicationSourceEvent
from .repository import PublicationLeaseRecord


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class PostgresPublicationMixin:
    @staticmethod
    def _event(row: Any | None) -> ControlTowerEvent | None:
        if row is None:
            return None
        data = dict(row)
        data["payload"] = _json(data["payload"])
        return ControlTowerEvent.model_validate(data)

    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent:
        with self._connection() as connection:
            latest = self._one(
                connection,
                """
                select evidence_hash from genesis_control_tower.control_tower_events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at desc, event_id desc limit 1
                """,
                (event.aggregate_type, event.aggregate_id),
            )
            expected = latest["evidence_hash"] if latest else None
            if event.previous_event_hash != expected:
                raise StateConflictError(
                    "Control Tower evidence does not continue the aggregate chain",
                    reason_codes=["EVIDENCE_CHAIN_CONFLICT"],
                )
            self._run(
                connection,
                """
                insert into genesis_control_tower.control_tower_events (
                  event_id, aggregate_type, aggregate_id, event_type, actor_id,
                  payload, occurred_at, previous_event_hash, evidence_hash
                ) values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                """,
                (
                    event.event_id,
                    event.aggregate_type,
                    event.aggregate_id,
                    event.event_type,
                    event.actor_id,
                    json.dumps(event.payload),
                    event.occurred_at,
                    event.previous_event_hash,
                    event.evidence_hash,
                ),
            )
        return event

    def latest_event(self, aggregate_type: str, aggregate_id: str) -> ControlTowerEvent | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select event_id, aggregate_type, aggregate_id, event_type, actor_id,
                       payload, occurred_at, previous_event_hash, evidence_hash
                from genesis_control_tower.control_tower_events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at desc, event_id desc limit 1
                """,
                (aggregate_type, aggregate_id),
            )
        return self._event(row)

    def lease_outbox(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        max_events: int,
        leased_at: datetime,
        expires_at: datetime,
    ) -> tuple[PublicationLeaseRecord, list[PublicationSourceEvent]]:
        with self._connection() as connection:
            self._run(
                connection,
                """
                update genesis_control_tower.publication_leases
                set status = 'EXPIRED'
                where status = 'LEASED' and expires_at <= %s
                """,
                (leased_at,),
            )
            rows = self._all(
                connection,
                """
                with source_events as (
                  select 'RUNTIME'::text as stream, event_id, aggregate_id, event_type,
                         evidence_hash, payload, occurred_at
                  from genesis_runtime.runtime_events where published_at is null
                  union all
                  select 'EDGE', event_id, node_id, event_type,
                         evidence_hash, payload, occurred_at
                  from genesis_edge.edge_evidence_events where published_at is null
                  union all
                  select 'CONTROL_TOWER', event_id, aggregate_id, event_type,
                         evidence_hash, payload, occurred_at
                  from genesis_control_tower.control_tower_events where published_at is null
                )
                select s.* from source_events s
                left join genesis_control_tower.publication_claims c
                  on c.stream::text = s.stream and c.source_event_id = s.event_id
                  and c.published_at is null and c.leased_until > %s
                where c.source_event_id is null
                order by s.occurred_at, s.stream, s.event_id
                limit %s
                """,
                (leased_at, max_events),
            )
            self._run(
                connection,
                """
                insert into genesis_control_tower.publication_leases (
                  lease_id, publisher_id, lease_token_hash, status, leased_at, expires_at
                ) values (%s,%s,%s,'LEASED',%s,%s)
                """,
                (lease_id, publisher_id, token_hash, leased_at, expires_at),
            )
            events: list[PublicationSourceEvent] = []
            keys: list[tuple[str, str]] = []
            for row in rows:
                event = PublicationSourceEvent.model_validate(
                    {
                        **dict(row),
                        "payload": _json(row["payload"]),
                    }
                )
                events.append(event)
                keys.append((event.stream.value, event.event_id))
                self._run(
                    connection,
                    """
                    insert into genesis_control_tower.publication_claims (
                      stream, source_event_id, lease_id, evidence_hash,
                      leased_until, attempts, updated_at
                    ) values (%s,%s,%s,%s,%s,1,%s)
                    on conflict (stream, source_event_id) do update set
                      lease_id = excluded.lease_id,
                      evidence_hash = excluded.evidence_hash,
                      leased_until = excluded.leased_until,
                      attempts = genesis_control_tower.publication_claims.attempts + 1,
                      updated_at = excluded.updated_at
                    where genesis_control_tower.publication_claims.published_at is null
                      and genesis_control_tower.publication_claims.leased_until <= %s
                    """,
                    (
                        event.stream.value,
                        event.event_id,
                        lease_id,
                        event.evidence_hash,
                        expires_at,
                        leased_at,
                        leased_at,
                    ),
                )
        return (
            PublicationLeaseRecord(
                lease_id=lease_id,
                publisher_id=publisher_id,
                token_hash=token_hash,
                status=PublicationLeaseStatus.LEASED,
                event_keys=keys,
                leased_at=leased_at,
                expires_at=expires_at,
            ),
            events,
        )

    def acknowledge_lease(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        items: list[PublicationAckItem],
        at: datetime,
    ) -> list[str]:
        with self._connection() as connection:
            lease = self._one(
                connection,
                """
                select lease_id, publisher_id, lease_token_hash, status, expires_at
                from genesis_control_tower.publication_leases
                where lease_id = %s for update
                """,
                (lease_id,),
            )
            if lease is None:
                raise NotFoundError("Publication lease was not found", reason_codes=["PUBLICATION_LEASE_NOT_FOUND"])
            if lease["status"] != "LEASED" or lease["expires_at"] <= at:
                raise StateConflictError("Publication lease is no longer active", reason_codes=["PUBLICATION_LEASE_INACTIVE"])
            if lease["publisher_id"] != publisher_id or not secrets.compare_digest(lease["lease_token_hash"], token_hash):
                raise StateConflictError("Publication lease credentials are invalid", reason_codes=["PUBLICATION_LEASE_INVALID"])
            claims = self._all(
                connection,
                """
                select stream::text as stream, source_event_id
                from genesis_control_tower.publication_claims
                where lease_id = %s and published_at is null
                order by stream, source_event_id
                """,
                (lease_id,),
            )
            expected = {(row["stream"], row["source_event_id"]) for row in claims}
            supplied = {(item.stream.value, item.event_id) for item in items}
            if expected != supplied:
                raise StateConflictError(
                    "Acknowledgement must cover exactly the events in the lease",
                    reason_codes=["PUBLICATION_ACK_SET_MISMATCH"],
                )
            for item in items:
                if item.stream.value == "RUNTIME":
                    table = "genesis_runtime.runtime_events"
                elif item.stream.value == "EDGE":
                    table = "genesis_edge.edge_evidence_events"
                else:
                    table = "genesis_control_tower.control_tower_events"
                self._run(connection, f"update {table} set published_at = %s, publication_attempts = publication_attempts + 1 where event_id = %s and published_at is null", (at, item.event_id))
                self._run(
                    connection,
                    """
                    update genesis_control_tower.publication_claims
                    set published_at = %s, destination_reference = %s, updated_at = %s
                    where stream = %s and source_event_id = %s and lease_id = %s
                    """,
                    (at, item.destination_reference, at, item.stream.value, item.event_id, lease_id),
                )
            self._run(
                connection,
                """
                update genesis_control_tower.publication_leases
                set status = 'ACKNOWLEDGED', acknowledged_at = %s
                where lease_id = %s
                """,
                (at, lease_id),
            )
        return [item.event_id for item in items]

    def unpublished_count(self, at: datetime) -> int:
        del at
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select
                  (select count(*) from genesis_runtime.runtime_events where published_at is null)
                  + (select count(*) from genesis_edge.edge_evidence_events where published_at is null)
                  + (select count(*) from genesis_control_tower.control_tower_events where published_at is null)
                  as count
                """,
            )
        return int(row["count"] if row else 0)

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
                where capability_id = %s and subject_id = %s
                  and resource_id in (%s, '*')
                  and allowed_action in (%s, 'CONTROL_TOWER_MANAGE', '*')
                  and expires_at > %s
                """,
                (capability_id, subject_id, resource_id, allowed_action, at),
            )
        if row is None:
            raise AuthorizationError(
                "Capability is missing, revoked, expired or does not match the requested operation",
                reason_codes=["CAPABILITY_INACTIVE"],
            )
        return CapabilityGrant.model_validate(row)
