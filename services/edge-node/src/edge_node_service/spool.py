from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
import uuid

from .models import SpoolEvent
from .signatures import spool_event_hash


class SQLiteEventSpool:
    """Durable local evidence spool for disconnected Edge Nodes."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma journal_mode = wal")
        connection.execute("pragma synchronous = full")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists edge_spool_events (
                  event_id text primary key,
                  sequence integer not null unique,
                  event_json text not null,
                  created_at text not null
                );
                create table if not exists edge_spool_meta (
                  key text primary key,
                  value text not null
                );
                insert or ignore into edge_spool_meta(key, value) values ('last_sequence', '0');
                insert or ignore into edge_spool_meta(key, value) values ('last_hash', '');
                """
            )

    def append(
        self,
        *,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
        occurred_at: datetime | None = None,
    ) -> SpoolEvent:
        at = occurred_at or datetime.now(timezone.utc)
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "select key, value from edge_spool_meta where key in ('last_sequence', 'last_hash')"
            ).fetchall()
            meta = {item["key"]: item["value"] for item in row}
            sequence = int(meta.get("last_sequence", "0")) + 1
            previous = meta.get("last_hash") or None
            provisional = SpoolEvent(
                event_id=f"spool-{uuid.uuid4().hex}",
                sequence=sequence,
                event_type=event_type,
                actor_id=actor_id,
                occurred_at=at,
                payload=payload,
                previous_local_hash=previous,
                local_hash="0" * 64,
            )
            event = provisional.model_copy(update={"local_hash": spool_event_hash(provisional)})
            connection.execute(
                "insert into edge_spool_events(event_id, sequence, event_json, created_at) values (?, ?, ?, ?)",
                (
                    event.event_id,
                    event.sequence,
                    event.model_dump_json(),
                    at.astimezone(timezone.utc).isoformat(),
                ),
            )
            connection.execute(
                "update edge_spool_meta set value = ? where key = 'last_sequence'",
                (str(sequence),),
            )
            connection.execute(
                "update edge_spool_meta set value = ? where key = 'last_hash'",
                (event.local_hash,),
            )
            return event

    def pending(self, limit: int = 100) -> list[SpoolEvent]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._connect() as connection:
            rows = connection.execute(
                "select event_json from edge_spool_events order by sequence limit ?",
                (limit,),
            ).fetchall()
        return [SpoolEvent.model_validate_json(row["event_json"]) for row in rows]

    def acknowledge(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        with self._lock, self._connect() as connection:
            connection.execute(
                f"delete from edge_spool_events where event_id in ({placeholders})",
                event_ids,
            )

    def next_heartbeat_sequence(self) -> int:
        with self._lock, self._connect() as connection:
            connection.execute(
                "insert or ignore into edge_spool_meta(key, value) values ('heartbeat_sequence', '0')"
            )
            row = connection.execute(
                "select value from edge_spool_meta where key = 'heartbeat_sequence'"
            ).fetchone()
            sequence = int(row["value"]) + 1
            connection.execute(
                "update edge_spool_meta set value = ? where key = 'heartbeat_sequence'",
                (str(sequence),),
            )
            return sequence

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("select count(*) from edge_spool_events").fetchone()[0])
