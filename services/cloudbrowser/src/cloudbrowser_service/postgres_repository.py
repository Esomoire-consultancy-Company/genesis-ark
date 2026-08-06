from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from typing import Any, Iterator

from .errors import NotFoundError, StateConflictError
from .models import (
    BrowserAction,
    BrowserActionRequest,
    BrowserApproval,
    BrowserPolicy,
    BrowserSession,
    EvidenceEvent,
    UsageRecord,
)


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class PostgresCloudBrowserRepository:
    """Authoritative PostgreSQL/Supabase repository for governed browser state."""

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
        if min_size < 0 or max_size < 1 or min_size > max_size:
            raise ValueError("invalid PostgreSQL pool size")
        self._timeout = timeout
        if pool is not None:
            self._pool = pool
            return
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - deployed package path
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
            name="genesis-cloudbrowser",
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
    def _advisory_lock(cls, connection: Any, session_id: str) -> None:
        cls._execute(
            connection,
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (session_id,),
        )

    def get_policy(self, policy_id: str) -> BrowserPolicy | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select policy_id, allowed_domains, allowed_actions,
                       high_impact_actions, allow_uploads, allow_downloads,
                       allow_clipboard, allow_credentials, allow_screen_capture,
                       allow_sensors, max_file_bytes
                from cloud_browser_policies
                where policy_id = %s and revoked_at is null
                  and effective_from <= now()
                  and (effective_until is null or effective_until > now())
                """,
                (policy_id,),
            )
        if not row:
            return None
        value = dict(row)
        for key in ("allowed_domains", "allowed_actions", "high_impact_actions"):
            value[key] = _decode_json(value[key])
        return BrowserPolicy.model_validate(value)

    def create_session(
        self,
        session: BrowserSession,
        usage: UsageRecord,
        event: EvidenceEvent,
    ) -> BrowserSession:
        with self._connection() as connection:
            self._advisory_lock(connection, session.browser_session_id)
            existing = self._fetchone(
                connection,
                "select browser_session_id from cloud_browser_sessions where browser_session_id = %s",
                (session.browser_session_id,),
            )
            if existing:
                raise StateConflictError("Browser session ID already exists")
            self._execute(
                connection,
                """
                insert into cloud_browser_sessions (
                  browser_session_id, box_id, digitalme_id, agent_id, context_id,
                  workspace_id, licence_id, runtime_id, policy_id,
                  policy_decision_id, capability_id, session_status,
                  isolation_profile, started_at, expires_at, terminated_at,
                  evidence_stream_id, compute_meter_id
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    session.browser_session_id,
                    session.box_id,
                    session.digitalme_id,
                    session.agent_id,
                    session.context_id,
                    session.workspace_id,
                    session.licence_id,
                    session.runtime_id,
                    session.policy_id,
                    session.policy_decision_id,
                    session.capability_id,
                    str(session.session_status),
                    session.isolation_profile,
                    session.started_at,
                    session.expires_at,
                    session.terminated_at,
                    session.evidence_stream_id,
                    session.compute_meter_id,
                ),
            )
            self._upsert_usage(connection, usage)
            self._append_evidence(connection, event)
        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "select * from cloud_browser_sessions where browser_session_id = %s",
                (session_id,),
            )
        return BrowserSession.model_validate(row) if row else None

    def transition_session(
        self,
        session: BrowserSession,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserSession:
        with self._connection() as connection:
            self._advisory_lock(connection, session.browser_session_id)
            row = self._fetchone(
                connection,
                "select browser_session_id from cloud_browser_sessions where browser_session_id = %s for update",
                (session.browser_session_id,),
            )
            if not row:
                raise NotFoundError(
                    f"Browser session {session.browser_session_id} does not exist"
                )
            self._append_evidence(connection, event)
            self._execute(
                connection,
                """
                update cloud_browser_sessions
                set session_status = %s, terminated_at = %s, updated_at = now()
                where browser_session_id = %s
                """,
                (
                    str(session.session_status),
                    session.terminated_at,
                    session.browser_session_id,
                ),
            )
            if usage is not None:
                self._upsert_usage(connection, usage)
        return session

    def record_action(
        self,
        action: BrowserAction,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserAction:
        with self._connection() as connection:
            self._advisory_lock(connection, action.browser_session_id)
            self._append_evidence(connection, event)
            self._upsert_action(connection, action)
            if usage is not None:
                self._upsert_usage(connection, usage)
        return action

    def record_approval_grant(
        self,
        approval: BrowserApproval,
        action: BrowserAction,
        approval_event: EvidenceEvent,
        usage: UsageRecord,
    ) -> BrowserAction:
        with self._connection() as connection:
            self._advisory_lock(connection, action.browser_session_id)
            existing = self._fetchone(
                connection,
                """
                select action_id, decision
                from cloud_browser_actions
                where action_id = %s
                for update
                """,
                (action.action_id,),
            )
            if not existing:
                raise NotFoundError(f"Browser action {action.action_id} does not exist")
            if existing["decision"] != "APPROVAL_REQUIRED":
                raise StateConflictError("Browser action is not awaiting approval")
            self._append_evidence(connection, approval_event)
            self._execute(
                connection,
                """
                insert into cloud_browser_approvals (
                  approval_id, browser_session_id, action_id, approved_by,
                  approval_reason, approved_at, expires_at, evidence_event_id
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    approval.approval_id,
                    approval.browser_session_id,
                    approval.action_id,
                    approval.approved_by,
                    approval.approval_reason,
                    approval.approved_at,
                    approval.expires_at,
                    approval.evidence_event_id,
                ),
            )
            self._upsert_action(connection, action)
            self._upsert_usage(connection, usage)
        return action

    def get_action(self, action_id: str) -> BrowserAction | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "select * from cloud_browser_actions where action_id = %s",
                (action_id,),
            )
        return self._action_from_row(row) if row else None

    def get_approval(self, approval_id: str) -> BrowserApproval | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select approval_id, browser_session_id, action_id, approved_by,
                       approval_reason, approved_at, expires_at, evidence_event_id
                from cloud_browser_approvals where approval_id = %s
                """,
                (approval_id,),
            )
        return BrowserApproval.model_validate(row) if row else None

    def get_usage(self, session_id: str) -> UsageRecord | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "select * from cloud_browser_usage where browser_session_id = %s",
                (session_id,),
            )
        return self._usage_from_row(row) if row else None

    def save_usage(self, usage: UsageRecord) -> UsageRecord:
        with self._connection() as connection:
            self._upsert_usage(connection, usage)
        return usage

    def append_evidence(self, event: EvidenceEvent) -> None:
        with self._connection() as connection:
            self._advisory_lock(connection, event.browser_session_id)
            self._append_evidence(connection, event)

    def latest_evidence(self, session_id: str) -> EvidenceEvent | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select event_id, browser_session_id, box_id, event_type,
                       actor_id, action_reference, occurred_at as timestamp,
                       payload, previous_event_hash, evidence_hash
                from cloud_browser_evidence_events
                where browser_session_id = %s
                order by occurred_at desc, event_id desc
                limit 1
                """,
                (session_id,),
            )
        return self._evidence_from_row(row) if row else None

    def list_evidence(self, session_id: str) -> list[EvidenceEvent]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select event_id, browser_session_id, box_id, event_type,
                       actor_id, action_reference, occurred_at as timestamp,
                       payload, previous_event_hash, evidence_hash
                from cloud_browser_evidence_events
                where browser_session_id = %s
                order by occurred_at, event_id
                """,
                (session_id,),
            )
        return [self._evidence_from_row(row) for row in rows]

    def list_session_actions(self, session_id: str) -> list[BrowserAction]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select * from cloud_browser_actions
                where browser_session_id = %s order by requested_at, action_id
                """,
                (session_id,),
            )
        return [self._action_from_row(row) for row in rows]

    @classmethod
    def _append_evidence(cls, connection: Any, event: EvidenceEvent) -> None:
        latest = cls._fetchone(
            connection,
            """
            select evidence_hash from cloud_browser_evidence_events
            where browser_session_id = %s
            order by occurred_at desc, event_id desc
            limit 1 for update
            """,
            (event.browser_session_id,),
        )
        expected = latest["evidence_hash"] if latest else None
        if event.previous_event_hash != expected:
            raise StateConflictError("Evidence event does not continue the session hash chain")
        cls._execute(
            connection,
            """
            insert into cloud_browser_evidence_events (
              event_id, browser_session_id, box_id, event_type, actor_id,
              action_reference, occurred_at, payload, previous_event_hash,
              evidence_hash
            ) values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                event.event_id,
                event.browser_session_id,
                event.box_id,
                event.event_type,
                event.actor_id,
                event.action_reference,
                event.timestamp,
                json.dumps(event.payload),
                event.previous_event_hash,
                event.evidence_hash,
            ),
        )

    @classmethod
    def _upsert_action(cls, connection: Any, action: BrowserAction) -> None:
        request_payload = action.request.model_dump(mode="json") if action.request else {}
        cls._execute(
            connection,
            """
            insert into cloud_browser_actions (
              action_id, browser_session_id, action_type, decision, reason_codes,
              target_url, warden_policy_decision_id, capability_id, approval_id,
              request_payload, result_payload, requested_at, decided_at,
              executed_at, evidence_event_id
            ) values (
              %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
              %s::jsonb, %s::jsonb, %s, %s, %s, %s
            )
            on conflict (action_id) do update set
              decision = excluded.decision,
              reason_codes = excluded.reason_codes,
              approval_id = excluded.approval_id,
              result_payload = excluded.result_payload,
              executed_at = excluded.executed_at,
              evidence_event_id = excluded.evidence_event_id
            """,
            (
                action.action_id,
                action.browser_session_id,
                str(action.action_type),
                str(action.decision),
                json.dumps(action.reason_codes),
                action.target_url,
                action.warden_policy_decision_id,
                action.capability_id,
                action.approval_id,
                json.dumps(request_payload),
                json.dumps(action.result) if action.result is not None else None,
                action.requested_at,
                action.decided_at,
                action.executed_at,
                action.evidence_event_id,
            ),
        )

    @classmethod
    def _upsert_usage(cls, connection: Any, usage: UsageRecord) -> None:
        cls._execute(
            connection,
            """
            insert into cloud_browser_usage (
              compute_meter_id, browser_session_id, runtime_seconds,
              action_count, approval_count, connector_calls, uploaded_bytes,
              downloaded_bytes, network_bytes, compute_units, updated_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (browser_session_id) do update set
              runtime_seconds = excluded.runtime_seconds,
              action_count = excluded.action_count,
              approval_count = excluded.approval_count,
              connector_calls = excluded.connector_calls,
              uploaded_bytes = excluded.uploaded_bytes,
              downloaded_bytes = excluded.downloaded_bytes,
              network_bytes = excluded.network_bytes,
              compute_units = excluded.compute_units,
              updated_at = excluded.updated_at
            """,
            (
                usage.compute_meter_id,
                usage.browser_session_id,
                usage.runtime_seconds,
                usage.action_count,
                usage.approval_count,
                usage.connector_calls,
                usage.uploaded_bytes,
                usage.downloaded_bytes,
                usage.network_bytes,
                usage.compute_units,
                usage.updated_at,
            ),
        )

    @staticmethod
    def _action_from_row(row: Any) -> BrowserAction:
        value = dict(row)
        value["reason_codes"] = _decode_json(value["reason_codes"])
        value["result"] = _decode_json(value.pop("result_payload"))
        request_payload = _decode_json(value.pop("request_payload"))
        for key in ("created_at",):
            value.pop(key, None)
        action = BrowserAction.model_validate(value)
        return action.bind_request(
            BrowserActionRequest.model_validate(request_payload)
            if request_payload
            else None
        )

    @staticmethod
    def _usage_from_row(row: Any) -> UsageRecord:
        value = dict(row)
        value["compute_units"] = float(value["compute_units"])
        return UsageRecord.model_validate(value)

    @staticmethod
    def _evidence_from_row(row: Any) -> EvidenceEvent:
        value = dict(row)
        value["payload"] = _decode_json(value["payload"])
        return EvidenceEvent.model_validate(value)
