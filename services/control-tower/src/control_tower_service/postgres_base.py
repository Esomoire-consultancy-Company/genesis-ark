from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import secrets
from threading import local
from typing import Any, Iterator

from .errors import AuthorizationError, NotFoundError, StateConflictError
from .models import (
    CapabilityGrant,
    ControlCommandRequest,
    ControlIncident,
    ControlTowerEvent,
    DispatchedEdgeCommand,
    FleetNodeSnapshot,
    PublicationAckItem,
    PublicationLeaseStatus,
    PublicationSourceEvent,
    SourceFleetObservation,
)
from .repository import PublicationLeaseRecord


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


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
            name="genesis-control-tower",
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
    def transaction(self, key: str) -> Iterator[None]:
        if getattr(self._local, "connection", None) is not None:
            raise RuntimeError("Nested Control Tower repository transactions are not supported")
        with self._pool.connection(timeout=self._timeout) as connection:
            with connection.transaction():
                self._run(
                    connection,
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"control-tower:{key}",),
                )
                self._local.connection = connection
                try:
                    yield
                finally:
                    del self._local.connection
