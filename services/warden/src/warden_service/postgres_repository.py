from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from typing import Any, Iterator

from .errors import NotFoundError, StateConflictError
from .models import (
    ActorBoxRecord,
    BindingRecord,
    BoundaryRuleRecord,
    CapabilityGrant,
    CapabilityStatus,
    ConsentRecord,
    ContextRecord,
    ControlStatus,
    DecisionRecord,
    DelegationRecord,
    EvidenceEvent,
    PolicyDecision,
    PolicyDecisionRequest,
    PolicyProfileRecord,
    Revocation,
    RuntimeRecord,
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class PostgresRegistry:
    """Authoritative PostgreSQL/Supabase adapter for Warden control state.

    All material writes use a single database transaction and a per-Box
    advisory transaction lock so evidence-chain continuation and state
    mutation cannot race each other.
    """

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
            raise ValueError("database_url is required for PostgresRegistry")
        if min_size < 0 or max_size < 1 or min_size > max_size:
            raise ValueError("invalid PostgreSQL pool size")
        self._timeout = timeout
        if pool is not None:
            self._pool = pool
            return
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - exercised in deployed package
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
            name="genesis-warden",
        )

    def open(self) -> None:
        open_method = getattr(self._pool, "open", None)
        if open_method is not None:
            open_method()
        wait_method = getattr(self._pool, "wait", None)
        if wait_method is not None:
            wait_method(timeout=self._timeout)

    def close(self) -> None:
        close_method = getattr(self._pool, "close", None)
        if close_method is not None:
            close_method()

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
    def _advisory_lock(cls, connection: Any, key: str) -> None:
        cls._execute(
            connection,
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )

    def get_box(self, box_id: str) -> ActorBoxRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select box_id, current_status as status, policy_profile_id,
                       evidence_stream_id, is_locked as locked, updated_at
                from actor_boxes where box_id = %s
                """,
                (box_id,),
            )
        return ActorBoxRecord.model_validate(row) if row else None

    def get_runtime(self, runtime_id: str) -> RuntimeRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select runtime_id, box_id, integrity_status, last_attested_at
                from box_runtimes where runtime_id = %s
                """,
                (runtime_id,),
            )
        return RuntimeRecord.model_validate(row) if row else None

    def get_runtime_for_box(self, box_id: str) -> RuntimeRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select runtime_id, box_id, integrity_status, last_attested_at
                from box_runtimes
                where box_id = %s
                order by last_attested_at desc, runtime_id
                limit 1
                """,
                (box_id,),
            )
        return RuntimeRecord.model_validate(row) if row else None

    def get_context(self, context_id: str) -> ContextRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select context_id, box_id, principal_id, workspace_id,
                       context_status as status, activated_at, expires_at
                from box_contexts where context_id = %s
                """,
                (context_id,),
            )
        return ContextRecord.model_validate(row) if row else None

    def get_active_context(self, box_id: str, at: datetime) -> ContextRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select context_id, box_id, principal_id, workspace_id,
                       context_status as status, activated_at, expires_at
                from box_contexts
                where box_id = %s and context_status = 'ACTIVE'
                  and activated_at <= %s
                  and (expires_at is null or expires_at > %s)
                order by activated_at desc, context_id
                limit 1
                """,
                (box_id, at, at),
            )
        return ContextRecord.model_validate(row) if row else None

    def get_policy_profile(self, policy_profile_id: str) -> PolicyProfileRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select policy_profile_id, box_id, policy_bundle_version,
                       profile_status as status, effective_from, effective_until,
                       max_capability_ttl_seconds
                from warden_policy_profiles where policy_profile_id = %s
                """,
                (policy_profile_id,),
            )
        return PolicyProfileRecord.model_validate(row) if row else None

    def find_binding(
        self,
        box_id: str,
        digitalme_id: str,
        at: datetime,
    ) -> BindingRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select binding_id, box_id, digitalme_id,
                       binding_status as status, effective_from, effective_until
                from actor_box_bindings
                where box_id = %s and digitalme_id = %s
                  and binding_status = 'ACTIVE'
                  and effective_from <= %s
                  and (effective_until is null or effective_until > %s)
                  and revoked_at is null
                order by effective_from desc, binding_id
                limit 1
                """,
                (box_id, digitalme_id, at, at),
            )
        return BindingRecord.model_validate(row) if row else None

    def find_consent(
        self,
        box_id: str,
        digitalme_id: str,
        at: datetime,
    ) -> ConsentRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select consent_receipt_id, box_id, digitalme_id, purpose,
                       data_scope, action_scope, 'ACTIVE' as status,
                       effective_from, effective_until
                from consent_receipts
                where box_id = %s and digitalme_id = %s
                  and receipt_status = 'ACTIVE'
                  and effective_from <= %s
                  and (effective_until is null or effective_until > %s)
                  and revoked_at is null
                order by effective_from desc, consent_receipt_id
                limit 1
                """,
                (box_id, digitalme_id, at, at),
            )
        if not row:
            return None
        row = dict(row)
        row["data_scope"] = _decode_json(row["data_scope"])
        row["action_scope"] = _decode_json(row["action_scope"])
        return ConsentRecord.model_validate(row)

    def find_delegation(
        self,
        box_id: str,
        agent_id: str,
        at: datetime,
    ) -> DelegationRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select delegation_id, box_id, agent_id, delegating_principal_id,
                       permitted_actions, permitted_data_scope, workspace_scope,
                       delegation_status as status, effective_from, effective_until,
                       write_requires_human_approval
                from delegated_agents
                where box_id = %s and agent_id = %s
                  and delegation_status = 'ACTIVE'
                  and effective_from <= %s
                  and (effective_until is null or effective_until > %s)
                  and revoked_at is null
                order by effective_from desc, delegation_id
                limit 1
                """,
                (box_id, agent_id, at, at),
            )
        if not row:
            return None
        row = dict(row)
        for key in ("permitted_actions", "permitted_data_scope", "workspace_scope"):
            row[key] = _decode_json(row[key])
        return DelegationRecord.model_validate(row)

    def boundary_rules(self, box_id: str, at: datetime) -> list[BoundaryRuleRecord]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select boundary_rule_id, box_id, source_zone, destination_zone,
                       data_class, permitted_purpose, rule_status as status,
                       effective_from, effective_until
                from data_boundary_rules
                where box_id = %s and rule_status = 'ACTIVE'
                  and effective_from <= %s
                  and (effective_until is null or effective_until > %s)
                  and revoked_at is null
                order by boundary_rule_id
                """,
                (box_id, at, at),
            )
        return [BoundaryRuleRecord.model_validate(row) for row in rows]

    def record_decision(self, record: DecisionRecord, event: EvidenceEvent) -> None:
        with self._connection() as connection:
            self._advisory_lock(connection, record.request.box_id)
            bound = self._fetchone(
                connection,
                "select 1 as present from actor_boxes where box_id = %s",
                (record.request.box_id,),
            ) is not None
            if bound:
                self._append_evidence(connection, event)
                self._execute(
                    connection,
                    """
                    insert into warden_policy_decisions (
                      policy_decision_id, request_id, box_id, runtime_id, subject_id,
                      agent_id, context_id, resource_id, requested_action, purpose,
                      outcome, reason_codes, policy_bundle_version, requested_at,
                      decided_at, evidence_event_id, request_payload, decision_payload
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                    )
                    """,
                    (
                        record.decision.policy_decision_id,
                        record.request.request_id,
                        record.request.box_id,
                        record.request.runtime_id,
                        record.request.subject_id,
                        record.request.agent_id,
                        record.request.context_id,
                        record.request.resource_id,
                        record.request.requested_action,
                        record.request.purpose,
                        str(record.decision.outcome),
                        json.dumps(record.decision.reason_codes),
                        record.decision.policy_bundle_version,
                        record.request.requested_at,
                        record.decision.decided_at,
                        event.event_id,
                        record.request.model_dump_json(),
                        record.decision.model_dump_json(),
                    ),
                )
            else:
                self._append_unbound_evidence(connection, event)
                self._execute(
                    connection,
                    """
                    insert into warden_unbound_decisions (
                      policy_decision_id, request_id, box_id, outcome, reason_codes,
                      policy_bundle_version, requested_at, decided_at,
                      evidence_event_id, request_payload, decision_payload
                    ) values (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (
                        record.decision.policy_decision_id,
                        record.request.request_id,
                        record.request.box_id,
                        str(record.decision.outcome),
                        json.dumps(record.decision.reason_codes),
                        record.decision.policy_bundle_version,
                        record.request.requested_at,
                        record.decision.decided_at,
                        event.event_id,
                        record.request.model_dump_json(),
                        record.decision.model_dump_json(),
                    ),
                )

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select request_payload, decision_payload
                from warden_policy_decisions where policy_decision_id = %s
                union all
                select request_payload, decision_payload
                from warden_unbound_decisions where policy_decision_id = %s
                limit 1
                """,
                (decision_id, decision_id),
            )
        if not row:
            return None
        return DecisionRecord(
            request=PolicyDecisionRequest.model_validate(_decode_json(row["request_payload"])),
            decision=PolicyDecision.model_validate(_decode_json(row["decision_payload"])),
        )

    def issue_capability(
        self,
        capability: CapabilityGrant,
        event: EvidenceEvent,
    ) -> CapabilityGrant:
        with self._connection() as connection:
            self._advisory_lock(connection, capability.box_id)
            existing = self._fetchone(
                connection,
                "select * from capability_grants where capability_id = %s for update",
                (capability.capability_id,),
            )
            if existing:
                return self._capability_from_row(existing)
            self._append_evidence(connection, event)
            self._execute(
                connection,
                """
                insert into capability_grants (
                  capability_id, box_id, subject_id, resource_id, allowed_action,
                  purpose, context_id, issued_at, expires_at, policy_decision_id,
                  capability_status, constraints
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    capability.capability_id,
                    capability.box_id,
                    capability.subject_id,
                    capability.resource_id,
                    capability.allowed_action,
                    capability.purpose,
                    capability.context_id,
                    capability.issued_at,
                    capability.expires_at,
                    capability.policy_decision_id,
                    str(capability.capability_status),
                    json.dumps(capability.constraints),
                ),
            )
        return capability

    def get_capability(self, capability_id: str) -> CapabilityGrant | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "select * from capability_grants where capability_id = %s",
                (capability_id,),
            )
        return self._capability_from_row(row) if row else None

    def revoke_capability(
        self,
        capability_id: str,
        revocation: Revocation,
        event: EvidenceEvent,
    ) -> None:
        with self._connection() as connection:
            self._advisory_lock(connection, revocation.box_id)
            row = self._fetchone(
                connection,
                "select capability_status from capability_grants where capability_id = %s for update",
                (capability_id,),
            )
            if not row:
                raise NotFoundError(f"Capability {capability_id} does not exist")
            if row["capability_status"] == CapabilityStatus.REVOKED:
                raise StateConflictError("Capability is already revoked")
            self._append_evidence(connection, event)
            self._execute(
                connection,
                """
                update capability_grants
                set capability_status = 'REVOKED', revoked_at = %s
                where capability_id = %s
                """,
                (revocation.effective_at, capability_id),
            )
            self._execute(
                connection,
                """
                insert into box_revocations (
                  revocation_id, box_id, target_type, target_id, reason,
                  revoked_by, effective_at, policy_reference, evidence_event_id
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    revocation.revocation_id,
                    revocation.box_id,
                    revocation.target_type,
                    revocation.target_id,
                    revocation.reason,
                    revocation.revoked_by,
                    revocation.effective_at,
                    revocation.policy_reference,
                    revocation.evidence_event_id,
                ),
            )

    def lock_box(
        self,
        box_id: str,
        at: datetime,
        reason: str,
        event: EvidenceEvent,
    ) -> None:
        with self._connection() as connection:
            self._advisory_lock(connection, box_id)
            row = self._fetchone(
                connection,
                "select is_locked from actor_boxes where box_id = %s for update",
                (box_id,),
            )
            if not row:
                raise NotFoundError(f"Actor Box {box_id} does not exist")
            if row["is_locked"]:
                raise StateConflictError("Actor Box is already locked")
            self._append_evidence(connection, event)
            self._execute(
                connection,
                """
                update actor_boxes
                set is_locked = true, locked_at = %s, lock_reason = %s,
                    current_status = 'SUSPENDED', updated_at = %s
                where box_id = %s
                """,
                (at, reason, at, box_id),
            )
            self._execute(
                connection,
                """
                update capability_grants
                set capability_status = 'SUSPENDED'
                where box_id = %s and capability_status = 'ISSUED'
                """,
                (box_id,),
            )

    def append_evidence(self, event: EvidenceEvent) -> None:
        with self._connection() as connection:
            self._advisory_lock(connection, event.box_id)
            bound = self._fetchone(
                connection,
                "select 1 as present from actor_boxes where box_id = %s",
                (event.box_id,),
            ) is not None
            if bound:
                self._append_evidence(connection, event)
            else:
                self._append_unbound_evidence(connection, event)

    def latest_evidence(self, box_id: str) -> EvidenceEvent | None:
        with self._connection() as connection:
            bound = self._fetchone(
                connection,
                "select 1 as present from actor_boxes where box_id = %s",
                (box_id,),
            ) is not None
            table = "box_evidence_events" if bound else "warden_unbound_evidence_events"
            row = self._fetchone(
                connection,
                f"""
                select event_id, box_id, event_type, actor_id, agent_id,
                       context_id, action_reference, policy_decision,
                       event_timestamp as timestamp, payload,
                       previous_event_hash, evidence_hash
                from {table}
                where box_id = %s
                order by event_timestamp desc, event_id desc
                limit 1
                """,
                (box_id,),
            )
        return self._evidence_from_row(row) if row else None

    def active_capabilities(self, box_id: str, at: datetime) -> list[CapabilityGrant]:
        del at
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                "select * from active_capability_grants where box_id = %s order by expires_at",
                (box_id,),
            )
        return [self._capability_from_row(row) for row in rows]

    def active_agent_count(self, box_id: str, at: datetime) -> int:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select count(distinct agent_id) as count
                from delegated_agents
                where box_id = %s and delegation_status = 'ACTIVE'
                  and effective_from <= %s
                  and (effective_until is null or effective_until > %s)
                  and revoked_at is null
                """,
                (box_id, at, at),
            )
        return int(row["count"]) if row else 0

    @classmethod
    def _append_evidence(cls, connection: Any, event: EvidenceEvent) -> None:
        latest = cls._fetchone(
            connection,
            """
            select evidence_hash from box_evidence_events
            where box_id = %s
            order by event_timestamp desc, event_id desc
            limit 1 for update
            """,
            (event.box_id,),
        )
        expected = latest["evidence_hash"] if latest else None
        if event.previous_event_hash != expected:
            raise StateConflictError("Evidence event does not continue the Box hash chain")
        cls._execute(
            connection,
            """
            insert into box_evidence_events (
              event_id, box_id, actor_id, agent_id, context_id, event_type,
              action_reference, policy_decision, event_timestamp, evidence_hash,
              previous_event_hash, custody_location, payload
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                event.event_id,
                event.box_id,
                event.actor_id,
                event.agent_id,
                event.context_id,
                event.event_type,
                event.action_reference,
                event.policy_decision,
                event.timestamp,
                event.evidence_hash,
                event.previous_event_hash,
                "RIVEROS:POSTGRES",
                json.dumps(event.payload),
            ),
        )

    @classmethod
    def _append_unbound_evidence(cls, connection: Any, event: EvidenceEvent) -> None:
        latest = cls._fetchone(
            connection,
            """
            select evidence_hash from warden_unbound_evidence_events
            where box_id = %s
            order by event_timestamp desc, event_id desc
            limit 1 for update
            """,
            (event.box_id,),
        )
        expected = latest["evidence_hash"] if latest else None
        if event.previous_event_hash != expected:
            raise StateConflictError("Evidence event does not continue the unbound Box hash chain")
        cls._execute(
            connection,
            """
            insert into warden_unbound_evidence_events (
              event_id, box_id, actor_id, agent_id, context_id, event_type,
              action_reference, policy_decision, event_timestamp, evidence_hash,
              previous_event_hash, payload
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                event.event_id, event.box_id, event.actor_id, event.agent_id,
                event.context_id, event.event_type, event.action_reference,
                event.policy_decision, event.timestamp, event.evidence_hash,
                event.previous_event_hash, json.dumps(event.payload),
            ),
        )

    @staticmethod
    def _capability_from_row(row: Any) -> CapabilityGrant:
        value = dict(row)
        value["constraints"] = _decode_json(value["constraints"])
        return CapabilityGrant.model_validate(value)

    @staticmethod
    def _evidence_from_row(row: Any) -> EvidenceEvent:
        value = dict(row)
        value["payload"] = _decode_json(value["payload"])
        return EvidenceEvent.model_validate(value)
