from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import secrets
from threading import local
from typing import Any, Iterator

from .errors import NotFoundError, StateConflictError
from .models import EdgeNodeIdentity, HeartbeatRequest


class PostgresBase:
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
        self._local = local()
        if pool is not None:
            self._pool = pool
            return
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError('PostgreSQL support requires "psycopg[binary,pool]"') from exc
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
            name="genesis-edge-node",
        )

    def open(self) -> None:
        if hasattr(self._pool, "open"):
            self._pool.open()
        if hasattr(self._pool, "wait"):
            self._pool.wait(timeout=self._timeout)

    def close(self) -> None:
        if hasattr(self._pool, "close"):
            self._pool.close()

    @staticmethod
    def _one(connection: Any, query: str, params: tuple[Any, ...] = ()) -> Any | None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @staticmethod
    def _all(connection: Any, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())

    @staticmethod
    def _run(connection: Any, query: str, params: tuple[Any, ...] = ()) -> None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        active = getattr(self._local, "connection", None)
        if active is not None:
            yield active
        else:
            with self._pool.connection(timeout=self._timeout) as connection:
                yield connection

    @contextmanager
    def transaction(self, node_id: str) -> Iterator[None]:
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("Nested Edge Node repository transactions are not supported")
        with self._pool.connection(timeout=self._timeout) as connection:
            with connection.transaction():
                self._run(
                    connection,
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"edge-node:{node_id}",),
                )
                self._local.connection = connection
                try:
                    yield
                finally:
                    del self._local.connection

    def consume_bootstrap_token(self, node_id: str, token_hash: str, at: datetime) -> None:
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select token_id, token_hash, expires_at
                from genesis_edge.edge_enrollment_tokens
                where node_id = %s and consumed_at is null
                order by created_at desc, token_id desc
                for update limit 1
                """,
                (node_id,),
            )
            if row is None:
                raise NotFoundError(
                    "No active enrollment token exists for this Runtime Node",
                    reason_codes=["BOOTSTRAP_TOKEN_NOT_FOUND"],
                )
            if row["expires_at"] <= at:
                raise StateConflictError(
                    "Enrollment token has expired",
                    reason_codes=["BOOTSTRAP_TOKEN_EXPIRED"],
                )
            if not secrets.compare_digest(row["token_hash"], token_hash):
                raise StateConflictError(
                    "Enrollment token is invalid",
                    reason_codes=["BOOTSTRAP_TOKEN_INVALID"],
                )
            self._run(
                connection,
                "update genesis_edge.edge_enrollment_tokens set consumed_at = %s where token_id = %s",
                (at, row["token_id"]),
            )

    def get_identity(self, node_id: str) -> EdgeNodeIdentity | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select node_id, device_id, agent_id, hardware_fingerprint,
                       agent_version, credential_reference, attestation_reference,
                       status, last_heartbeat_sequence, last_spool_sequence,
                       last_spool_hash, last_seen_at, enrolled_at, updated_at
                from genesis_edge.edge_node_identities where node_id = %s
                """,
                (node_id,),
            )
        return EdgeNodeIdentity.model_validate(row) if row else None

    def save_identity(self, identity: EdgeNodeIdentity) -> EdgeNodeIdentity:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_edge.edge_node_identities (
                  node_id, device_id, agent_id, hardware_fingerprint,
                  agent_version, credential_reference, attestation_reference,
                  status, last_heartbeat_sequence, last_spool_sequence,
                  last_spool_hash, last_seen_at, enrolled_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (node_id) do update set
                  agent_version = excluded.agent_version,
                  credential_reference = excluded.credential_reference,
                  attestation_reference = excluded.attestation_reference,
                  status = excluded.status,
                  last_heartbeat_sequence = excluded.last_heartbeat_sequence,
                  last_spool_sequence = excluded.last_spool_sequence,
                  last_spool_hash = excluded.last_spool_hash,
                  last_seen_at = excluded.last_seen_at,
                  updated_at = excluded.updated_at
                """,
                (
                    identity.node_id,
                    identity.device_id,
                    identity.agent_id,
                    identity.hardware_fingerprint,
                    identity.agent_version,
                    identity.credential_reference,
                    identity.attestation_reference,
                    identity.status.value,
                    identity.last_heartbeat_sequence,
                    identity.last_spool_sequence,
                    identity.last_spool_hash,
                    identity.last_seen_at,
                    identity.enrolled_at,
                    identity.updated_at,
                ),
            )
        return identity

    def save_heartbeat(self, node_id: str, heartbeat: HeartbeatRequest, accepted_at: datetime) -> None:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_edge.edge_heartbeats (
                  node_id, sequence, sent_at, accepted_at, agent_version,
                  attestation_reference, runtime_digest, node_state, metrics, signature
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                """,
                (
                    node_id,
                    heartbeat.sequence,
                    heartbeat.sent_at,
                    accepted_at,
                    heartbeat.agent_version,
                    heartbeat.attestation_reference,
                    heartbeat.runtime_digest,
                    heartbeat.node_state.value,
                    json.dumps(heartbeat.metrics),
                    heartbeat.signature,
                ),
            )
