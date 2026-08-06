from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from threading import local
from typing import Any, Iterator

from .errors import StateConflictError
from .models import CapabilityAuthorization, ControlTowerEvent, FleetAsset, FleetCommand, Incident


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _decode_fields(row: Any, *fields: str) -> Any:
    if row is None:
        return None
    result = dict(row)
    for field in fields:
        result[field] = _decode_json(result[field])
    return result

class PostgresControlTowerBase:
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
        self._state = local()
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

    @contextmanager
    def transaction(self, aggregate_key: str) -> Iterator[None]:
        active = getattr(self._state, "connection", None)
        if active is not None:
            self._execute(
                active,
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (aggregate_key,),
            )
            yield
            return
        with self._pool.connection(timeout=self._timeout) as connection:
            self._state.connection = connection
            try:
                self._execute(
                    connection,
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (aggregate_key,),
                )
                yield
            finally:
                self._state.connection = None

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        active = getattr(self._state, "connection", None)
        if active is not None:
            yield active
            return
        with self._pool.connection(timeout=self._timeout) as connection:
            yield connection

    @staticmethod
    def _execute(connection: Any, query: str, params: tuple[Any, ...] = ()) -> None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

    @staticmethod
    def _fetchone(connection: Any, query: str, params: tuple[Any, ...]) -> Any | None:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @staticmethod
    def _fetchall(connection: Any, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())
