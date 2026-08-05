from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import secrets
from threading import RLock
from typing import ContextManager, Iterator, Protocol

from .errors import NotFoundError, StateConflictError
from .models import (
    CommandStatus,
    CompletionStatus,
    EdgeCommand,
    EdgeEvidenceEvent,
    EdgeNodeIdentity,
    HeartbeatRequest,
    SpoolEvent,
)


class EdgeNodeRepository(Protocol):
    def transaction(self, node_id: str) -> ContextManager[None]: ...
    def consume_bootstrap_token(self, node_id: str, token_hash: str, at: datetime) -> None: ...
    def get_identity(self, node_id: str) -> EdgeNodeIdentity | None: ...
    def save_identity(self, identity: EdgeNodeIdentity) -> EdgeNodeIdentity: ...
    def save_heartbeat(self, node_id: str, heartbeat: HeartbeatRequest, accepted_at: datetime) -> None: ...
    def get_command(self, command_id: str) -> EdgeCommand | None: ...
    def save_command(self, command: EdgeCommand) -> EdgeCommand: ...
    def lease_next_command(
        self,
        *,
        node_id: str,
        agent_id: str,
        at: datetime,
        lease_seconds: int,
        lease_token_hash: str,
        max_attempts: int,
    ) -> EdgeCommand | None: ...
    def complete_command(
        self,
        *,
        node_id: str,
        command_id: str,
        agent_id: str,
        lease_token_hash: str,
        status: CompletionStatus,
        result: dict[str, object],
        at: datetime,
    ) -> EdgeCommand: ...
    def ingest_spool_event(self, node_id: str, event: SpoolEvent, at: datetime) -> bool: ...
    def append_event(self, event: EdgeEvidenceEvent) -> EdgeEvidenceEvent: ...
    def latest_event(self, node_id: str) -> EdgeEvidenceEvent | None: ...
    def list_events(self, node_id: str) -> list[EdgeEvidenceEvent]: ...


class InMemoryEdgeNodeRepository:
    def __init__(self) -> None:
        self.identities: dict[str, EdgeNodeIdentity] = {}
        self.bootstrap_tokens: dict[str, tuple[str, datetime]] = {}
        self.heartbeats: dict[str, list[HeartbeatRequest]] = {}
        self.commands: dict[str, EdgeCommand] = {}
        self.spool_events: dict[str, tuple[str, SpoolEvent]] = {}
        self.events: list[EdgeEvidenceEvent] = []
        self._lock = RLock()

    def seed_bootstrap_token(self, node_id: str, raw_token: str, expires_at: datetime) -> None:
        self.bootstrap_tokens[node_id] = (
            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at,
        )

    @contextmanager
    def transaction(self, node_id: str) -> Iterator[None]:
        del node_id
        with self._lock:
            snapshot = deepcopy(
                (
                    self.identities,
                    self.bootstrap_tokens,
                    self.heartbeats,
                    self.commands,
                    self.spool_events,
                    self.events,
                )
            )
            try:
                yield
            except Exception:
                (
                    self.identities,
                    self.bootstrap_tokens,
                    self.heartbeats,
                    self.commands,
                    self.spool_events,
                    self.events,
                ) = snapshot
                raise

    def consume_bootstrap_token(self, node_id: str, token_hash: str, at: datetime) -> None:
        token = self.bootstrap_tokens.get(node_id)
        if token is None:
            raise NotFoundError(
                "No active enrollment token exists for this Runtime Node",
                reason_codes=["BOOTSTRAP_TOKEN_NOT_FOUND"],
            )
        expected_hash, expires_at = token
        if expires_at <= at:
            raise StateConflictError(
                "Enrollment token has expired",
                reason_codes=["BOOTSTRAP_TOKEN_EXPIRED"],
            )
        if not secrets.compare_digest(expected_hash, token_hash):
            raise StateConflictError(
                "Enrollment token is invalid",
                reason_codes=["BOOTSTRAP_TOKEN_INVALID"],
            )
        del self.bootstrap_tokens[node_id]

    def get_identity(self, node_id: str) -> EdgeNodeIdentity | None:
        return self.identities.get(node_id)

    def save_identity(self, identity: EdgeNodeIdentity) -> EdgeNodeIdentity:
        self.identities[identity.node_id] = identity
        return identity

    def save_heartbeat(self, node_id: str, heartbeat: HeartbeatRequest, accepted_at: datetime) -> None:
        del accepted_at
        self.heartbeats.setdefault(node_id, []).append(heartbeat)

    def get_command(self, command_id: str) -> EdgeCommand | None:
        return self.commands.get(command_id)

    def save_command(self, command: EdgeCommand) -> EdgeCommand:
        if command.command_id in self.commands:
            raise StateConflictError(
                "Command already exists",
                reason_codes=["COMMAND_ID_CONFLICT"],
            )
        self.commands[command.command_id] = command
        return command

    def lease_next_command(
        self,
        *,
        node_id: str,
        agent_id: str,
        at: datetime,
        lease_seconds: int,
        lease_token_hash: str,
        max_attempts: int,
    ) -> EdgeCommand | None:
        from datetime import timedelta

        candidates = sorted(
            (
                command
                for command in self.commands.values()
                if command.node_id == node_id
                and command.status in {CommandStatus.PENDING, CommandStatus.LEASED}
                and command.expires_at > at
                and command.attempts < max_attempts
                and (
                    command.status == CommandStatus.PENDING
                    or command.lease_expires_at is None
                    or command.lease_expires_at <= at
                )
            ),
            key=lambda item: (item.issued_at, item.command_id),
        )
        if not candidates:
            return None
        command = candidates[0].model_copy(
            update={
                "status": CommandStatus.LEASED,
                "attempts": candidates[0].attempts + 1,
                "lease_owner": agent_id,
                "lease_token_hash": lease_token_hash,
                "lease_expires_at": at + timedelta(seconds=lease_seconds),
                "updated_at": at,
            }
        )
        self.commands[command.command_id] = command
        return command

    def complete_command(
        self,
        *,
        node_id: str,
        command_id: str,
        agent_id: str,
        lease_token_hash: str,
        status: CompletionStatus,
        result: dict[str, object],
        at: datetime,
    ) -> EdgeCommand:
        command = self.commands.get(command_id)
        if command is None or command.node_id != node_id:
            raise NotFoundError(
                "Command was not found for this node",
                reason_codes=["COMMAND_NOT_FOUND"],
            )
        if command.status != CommandStatus.LEASED:
            raise StateConflictError(
                "Command is not leased",
                reason_codes=["COMMAND_NOT_LEASED"],
            )
        if command.lease_owner != agent_id:
            raise StateConflictError(
                "Command lease belongs to another agent",
                reason_codes=["LEASE_OWNER_MISMATCH"],
            )
        if command.lease_token_hash is None or not secrets.compare_digest(
            command.lease_token_hash,
            lease_token_hash,
        ):
            raise StateConflictError(
                "Command lease token is invalid",
                reason_codes=["LEASE_TOKEN_INVALID"],
            )
        if command.lease_expires_at is None or command.lease_expires_at <= at:
            raise StateConflictError(
                "Command lease has expired",
                reason_codes=["LEASE_EXPIRED"],
            )
        updated = command.model_copy(
            update={
                "status": CommandStatus(status.value),
                "completed_at": at,
                "result": result,
                "updated_at": at,
            }
        )
        self.commands[command_id] = updated
        return updated

    def ingest_spool_event(self, node_id: str, event: SpoolEvent, at: datetime) -> bool:
        del at
        existing = self.spool_events.get(event.event_id)
        if existing is not None:
            existing_node, existing_event = existing
            if existing_node != node_id or existing_event.local_hash != event.local_hash:
                raise StateConflictError(
                    "Spool event ID conflicts with previously ingested content",
                    reason_codes=["SPOOL_EVENT_ID_CONFLICT"],
                )
            return False
        self.spool_events[event.event_id] = (node_id, event)
        return True

    def append_event(self, event: EdgeEvidenceEvent) -> EdgeEvidenceEvent:
        latest = self.latest_event(event.node_id)
        expected = latest.evidence_hash if latest is not None else None
        if event.previous_event_hash != expected:
            raise StateConflictError(
                "Edge evidence event does not continue the node chain",
                reason_codes=["EVIDENCE_CHAIN_CONFLICT"],
            )
        self.events.append(event)
        return event

    def latest_event(self, node_id: str) -> EdgeEvidenceEvent | None:
        return next((event for event in reversed(self.events) if event.node_id == node_id), None)

    def list_events(self, node_id: str) -> list[EdgeEvidenceEvent]:
        return [event for event in self.events if event.node_id == node_id]
