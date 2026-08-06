from __future__ import annotations

from datetime import datetime, timedelta
import json
import secrets
from typing import Any

from .errors import NotFoundError, StateConflictError
from .models import CommandStatus, CompletionStatus, EdgeCommand

_COMMAND_COLUMNS = """
command_id, node_id, command_type, capability_id,
required_capability_action, issued_by, target_reference,
payload, status, attempts, issued_at, expires_at,
lease_owner, lease_token_hash, lease_expires_at,
completed_at, result, updated_at
"""


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _command(row: Any) -> EdgeCommand | None:
    if row is None:
        return None
    data = dict(row)
    data["payload"] = _json(data["payload"])
    data["result"] = _json(data["result"]) if data.get("result") is not None else None
    return EdgeCommand.model_validate(data)


class PostgresCommandMixin:
    def get_command(self, command_id: str) -> EdgeCommand | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                f"select {_COMMAND_COLUMNS} from genesis_edge.edge_commands where command_id = %s",
                (command_id,),
            )
        return _command(row)

    def save_command(self, command: EdgeCommand) -> EdgeCommand:
        with self._connection() as connection:
            try:
                self._run(
                    connection,
                    """
                    insert into genesis_edge.edge_commands (
                      command_id, node_id, command_type, capability_id,
                      required_capability_action, issued_by, target_reference,
                      payload, status, attempts, issued_at, expires_at,
                      lease_owner, lease_token_hash, lease_expires_at,
                      completed_at, result, updated_at
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                    """,
                    (
                        command.command_id,
                        command.node_id,
                        command.command_type.value,
                        command.capability_id,
                        command.required_capability_action,
                        command.issued_by,
                        command.target_reference,
                        json.dumps(command.payload),
                        command.status.value,
                        command.attempts,
                        command.issued_at,
                        command.expires_at,
                        command.lease_owner,
                        command.lease_token_hash,
                        command.lease_expires_at,
                        command.completed_at,
                        json.dumps(command.result) if command.result is not None else None,
                        command.updated_at,
                    ),
                )
            except Exception as exc:
                raise StateConflictError(
                    "Command already exists",
                    reason_codes=["COMMAND_ID_CONFLICT"],
                ) from exc
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
        with self._connection() as connection:
            candidate = self._one(
                connection,
                """
                select command_id from genesis_edge.edge_commands
                where node_id = %s and expires_at > %s and attempts < %s
                  and (status = 'PENDING' or (status = 'LEASED' and lease_expires_at <= %s))
                order by issued_at, command_id
                for update skip locked limit 1
                """,
                (node_id, at, max_attempts, at),
            )
            if candidate is None:
                return None
            row = self._one(
                connection,
                f"""
                update genesis_edge.edge_commands
                set status = 'LEASED', attempts = attempts + 1,
                    lease_owner = %s, lease_token_hash = %s,
                    lease_expires_at = %s, updated_at = %s
                where command_id = %s returning {_COMMAND_COLUMNS}
                """,
                (
                    agent_id,
                    lease_token_hash,
                    at + timedelta(seconds=lease_seconds),
                    at,
                    candidate["command_id"],
                ),
            )
        return _command(row)

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
        with self._connection() as connection:
            current = _command(
                self._one(
                    connection,
                    f"select {_COMMAND_COLUMNS} from genesis_edge.edge_commands where command_id = %s and node_id = %s for update",
                    (command_id, node_id),
                )
            )
            if current is None:
                raise NotFoundError("Command was not found for this node", reason_codes=["COMMAND_NOT_FOUND"])
            if current.status != CommandStatus.LEASED:
                raise StateConflictError("Command is not leased", reason_codes=["COMMAND_NOT_LEASED"])
            if current.lease_owner != agent_id:
                raise StateConflictError("Command lease belongs to another agent", reason_codes=["LEASE_OWNER_MISMATCH"])
            if current.lease_token_hash is None or not secrets.compare_digest(current.lease_token_hash, lease_token_hash):
                raise StateConflictError("Command lease token is invalid", reason_codes=["LEASE_TOKEN_INVALID"])
            if current.lease_expires_at is None or current.lease_expires_at <= at:
                raise StateConflictError("Command lease has expired", reason_codes=["LEASE_EXPIRED"])
            row = self._one(
                connection,
                f"""
                update genesis_edge.edge_commands
                set status = %s, completed_at = %s, result = %s::jsonb, updated_at = %s
                where command_id = %s returning {_COMMAND_COLUMNS}
                """,
                (status.value, at, json.dumps(result), at, command_id),
            )
        completed = _command(row)
        assert completed is not None
        return completed
