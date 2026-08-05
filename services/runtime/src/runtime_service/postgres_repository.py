from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from typing import Any, Iterator

from .errors import StateConflictError
from .models import (
    CapabilityAuthorization,
    RecoveryJob,
    ResourceAllocation,
    ResourceVector,
    RuntimeEvent,
    RuntimeHealthReport,
    RuntimeInstance,
    RuntimeNode,
    RuntimeSession,
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _with_resource(row: Any, key: str) -> Any:
    if row is None:
        return None
    result = dict(row)
    result[key] = _decode_json(result[key])
    return result


class PostgresRuntimeRepository:
    """Authoritative PostgreSQL/Supabase runtime repository and capability verifier."""

    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 8,
        timeout: float = 10.0,
        prepare_threshold: int | None = None,
        pool: Any | None = None,
    ) -> None:
        if not database_url and pool is None:
            raise ValueError("database_url is required")
        self._timeout = timeout
        if pool is not None:
            self._pool = pool
            return
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                'PostgreSQL support requires "psycopg[binary,pool]"'
            ) from exc
        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "prepare_threshold": prepare_threshold,
                "autocommit": False,
            },
            name="genesis-runtime-manager",
        )

    def open(self) -> None:
        if hasattr(self._pool, "open"):
            self._pool.open()
        if hasattr(self._pool, "wait"):
            self._pool.wait(timeout=self._timeout)

    def close(self) -> None:
        if hasattr(self._pool, "close"):
            self._pool.close()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self._pool.connection(timeout=self._timeout) as connection:
            yield connection

    @staticmethod
    def _fetchone(connection: Any, query: str, params: tuple[Any, ...]) -> Any | None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @staticmethod
    def _fetchall(connection: Any, query: str, params: tuple[Any, ...]) -> list[Any]:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())

    @staticmethod
    def _execute(connection: Any, query: str, params: tuple[Any, ...] = ()) -> None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    @classmethod
    def _lock(cls, connection: Any, key: str) -> None:
        cls._execute(
            connection,
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )

    def get_node(self, node_id: str) -> RuntimeNode | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select node_id, node_class, region, jurisdiction,
                       authority_reference, attestation_reference, status,
                       capacity, registered_at, updated_at
                from genesis_runtime.runtime_nodes where node_id = %s
                """,
                (node_id,),
            )
        return RuntimeNode.model_validate(_with_resource(row, "capacity")) if row else None

    def save_node(self, node: RuntimeNode) -> RuntimeNode:
        with self._connection() as connection:
            try:
                self._execute(
                    connection,
                    """
                    insert into genesis_runtime.runtime_nodes (
                      node_id, node_class, region, jurisdiction,
                      authority_reference, attestation_reference, status,
                      capacity, registered_at, updated_at
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                    """,
                    (
                        node.node_id, node.node_class, node.region, node.jurisdiction,
                        node.authority_reference, node.attestation_reference, node.status,
                        json.dumps(node.capacity.model_dump()), node.registered_at, node.updated_at,
                    ),
                )
            except Exception as exc:
                raise StateConflictError("Runtime node already exists") from exc
        return node

    def get_instance(self, instance_id: str) -> RuntimeInstance | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select instance_id, node_id, box_id, runtime_class, runtime_version,
                       status, integrity_status, resource_limits,
                       attestation_reference, provisioned_at, activated_at,
                       last_attested_at, updated_at
                from genesis_runtime.runtime_instances where instance_id = %s
                """,
                (instance_id,),
            )
        return RuntimeInstance.model_validate(_with_resource(row, "resource_limits")) if row else None

    def save_instance(self, instance: RuntimeInstance) -> RuntimeInstance:
        with self._connection() as connection:
            self._lock(connection, f"runtime-instance:{instance.instance_id}")
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_instances (
                  instance_id, node_id, box_id, runtime_class, runtime_version,
                  status, integrity_status, resource_limits, attestation_reference,
                  provisioned_at, activated_at, last_attested_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                on conflict (instance_id) do update set
                  status = excluded.status,
                  integrity_status = excluded.integrity_status,
                  resource_limits = excluded.resource_limits,
                  attestation_reference = excluded.attestation_reference,
                  activated_at = excluded.activated_at,
                  last_attested_at = excluded.last_attested_at,
                  updated_at = excluded.updated_at
                """,
                (
                    instance.instance_id, instance.node_id, instance.box_id,
                    instance.runtime_class, instance.runtime_version, instance.status,
                    instance.integrity_status,
                    json.dumps(instance.resource_limits.model_dump()),
                    instance.attestation_reference, instance.provisioned_at,
                    instance.activated_at, instance.last_attested_at, instance.updated_at,
                ),
            )
        return instance

    def get_session(self, session_id: str) -> RuntimeSession | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select session_id, instance_id, box_id, principal_id, context_id,
                       capability_id, session_type, purpose, status, started_at,
                       expires_at, terminated_at, termination_reason, updated_at
                from genesis_runtime.runtime_sessions where session_id = %s
                """,
                (session_id,),
            )
        return RuntimeSession.model_validate(row) if row else None

    def save_session(self, session: RuntimeSession) -> RuntimeSession:
        with self._connection() as connection:
            self._lock(connection, f"runtime-session:{session.session_id}")
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_sessions (
                  session_id, instance_id, box_id, principal_id, context_id,
                  capability_id, session_type, purpose, status, started_at,
                  expires_at, terminated_at, termination_reason, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (session_id) do update set
                  status = excluded.status,
                  terminated_at = excluded.terminated_at,
                  termination_reason = excluded.termination_reason,
                  updated_at = excluded.updated_at
                """,
                (
                    session.session_id, session.instance_id, session.box_id,
                    session.principal_id, session.context_id, session.capability_id,
                    session.session_type, session.purpose, session.status,
                    session.started_at, session.expires_at, session.terminated_at,
                    session.termination_reason, session.updated_at,
                ),
            )
        return session

    def save_allocation(self, allocation: ResourceAllocation) -> ResourceAllocation:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_resource_allocations (
                  allocation_id, session_id, capability_id, resources,
                  status, allocated_at, released_at
                ) values (%s,%s,%s,%s::jsonb,%s,%s,%s)
                """,
                (
                    allocation.allocation_id, allocation.session_id,
                    allocation.capability_id, json.dumps(allocation.resources.model_dump()),
                    allocation.status, allocation.allocated_at, allocation.released_at,
                ),
            )
        return allocation

    def active_allocations_for_instance(
        self,
        instance_id: str,
        at: datetime,
    ) -> list[ResourceAllocation]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select a.allocation_id, a.session_id, a.capability_id,
                       a.resources, a.status, a.allocated_at, a.released_at
                from genesis_runtime.runtime_resource_allocations a
                join genesis_runtime.runtime_sessions s on s.session_id = a.session_id
                where s.instance_id = %s and s.status = 'ACTIVE'
                  and s.started_at <= %s and s.expires_at > %s
                  and a.status = 'ACTIVE'
                """,
                (instance_id, at, at),
            )
        return [
            ResourceAllocation.model_validate(_with_resource(row, "resources"))
            for row in rows
        ]

    def node_reserved_resources(self, node_id: str) -> ResourceVector:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select resource_limits
                from genesis_runtime.runtime_instances
                where node_id = %s and status not in ('STOPPED','RETIRED')
                """,
                (node_id,),
            )
        total = ResourceVector()
        for row in rows:
            total = total.plus(ResourceVector.model_validate(_decode_json(row["resource_limits"])))
        return total

    def release_allocations_for_session(self, session_id: str, at: datetime) -> None:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                update genesis_runtime.runtime_resource_allocations
                set status = 'RELEASED', released_at = %s
                where session_id = %s and status = 'ACTIVE'
                """,
                (at, session_id),
            )

    def save_health_report(self, report: RuntimeHealthReport) -> RuntimeHealthReport:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_health_reports (
                  health_report_id, instance_id, state, reported_by,
                  checks, metrics, reported_at
                ) values (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                """,
                (
                    report.health_report_id, report.instance_id, report.state,
                    report.reported_by, json.dumps(report.checks),
                    json.dumps(report.metrics), report.reported_at,
                ),
            )
        return report

    def save_recovery_job(self, job: RecoveryJob) -> RecoveryJob:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_recovery_jobs (
                  recovery_job_id, instance_id, status,
                  trigger_health_report_id, required_capability_action,
                  created_at, authorized_at
                ) values (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    job.recovery_job_id, job.instance_id, job.status,
                    job.trigger_health_report_id, job.required_capability_action,
                    job.created_at, job.authorized_at,
                ),
            )
        return job

    def append_event(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._connection() as connection:
            key = f"runtime-event:{event.aggregate_type}:{event.aggregate_id}"
            self._lock(connection, key)
            latest = self._fetchone(
                connection,
                """
                select evidence_hash
                from genesis_runtime.runtime_events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at desc, event_id desc limit 1
                """,
                (event.aggregate_type, event.aggregate_id),
            )
            expected = latest["evidence_hash"] if latest else None
            if event.previous_event_hash != expected:
                raise StateConflictError("Runtime event does not continue the evidence chain")
            self._execute(
                connection,
                """
                insert into genesis_runtime.runtime_events (
                  event_id, aggregate_type, aggregate_id, box_id, event_type,
                  payload, occurred_at, previous_event_hash, evidence_hash, published_at
                ) values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                """,
                (
                    event.event_id, event.aggregate_type, event.aggregate_id,
                    event.box_id, event.event_type, json.dumps(event.payload),
                    event.occurred_at, event.previous_event_hash,
                    event.evidence_hash, event.published_at,
                ),
            )
        return event

    def latest_event(self, aggregate_type: str, aggregate_id: str) -> RuntimeEvent | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select event_id, aggregate_type, aggregate_id, box_id, event_type,
                       payload, occurred_at, previous_event_hash, evidence_hash, published_at
                from genesis_runtime.runtime_events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at desc, event_id desc limit 1
                """,
                (aggregate_type, aggregate_id),
            )
        if not row:
            return None
        result = dict(row)
        result["payload"] = _decode_json(result["payload"])
        return RuntimeEvent.model_validate(result)

    def list_events(self, aggregate_type: str, aggregate_id: str) -> list[RuntimeEvent]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select event_id, aggregate_type, aggregate_id, box_id, event_type,
                       payload, occurred_at, previous_event_hash, evidence_hash, published_at
                from genesis_runtime.runtime_events
                where aggregate_type = %s and aggregate_id = %s
                order by occurred_at, event_id
                """,
                (aggregate_type, aggregate_id),
            )
        return [
            RuntimeEvent.model_validate({**dict(row), "payload": _decode_json(row["payload"])})
            for row in rows
        ]

    def verify(
        self,
        *,
        capability_id: str,
        box_id: str,
        principal_id: str,
        context_id: str,
        resource_id: str,
        required_actions: set[str],
        purpose: str,
        at: datetime,
    ) -> CapabilityAuthorization | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select capability_id, box_id, subject_id, context_id, resource_id,
                       allowed_action, purpose, expires_at, constraints
                from public.active_capability_grants
                where capability_id = %s and box_id = %s and subject_id = %s
                  and context_id = %s and purpose = %s and expires_at > %s
                """,
                (capability_id, box_id, principal_id, context_id, purpose, at),
            )
        if not row:
            return None
        allowed = row["allowed_action"]
        if allowed not in required_actions | {"RUNTIME_MANAGE", "*"}:
            return None
        if row["resource_id"] not in {resource_id, box_id, "*"}:
            return None
        result = dict(row)
        result["constraints"] = _decode_json(result["constraints"])
        return CapabilityAuthorization.model_validate(result)
