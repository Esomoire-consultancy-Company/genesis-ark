from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .errors import StateConflictError
from .models import CapabilityAuthorization, ControlTowerEvent, FleetAsset, FleetCommand, Incident
from .postgres_base import _decode_fields, _decode_json

class PostgresCommandOperations:
    def get_command(self, command_id: str) -> FleetCommand | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select command_id, target_asset_id, command_type, issuer_id,
                       box_id, context_id, capability_id, purpose, parameters,
                       status, high_impact, issued_at, expires_at, approved_by,
                       approval_capability_id, approval_reason, approved_at,
                       dispatched_at, completed_at, result, updated_at
                from genesis_control_tower.fleet_commands where command_id = %s
                """,
                (command_id,),
            )
        decoded = _decode_fields(row, "parameters", "result")
        return FleetCommand.model_validate(decoded) if decoded else None

    def save_command(self, command: FleetCommand) -> FleetCommand:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_control_tower.fleet_commands (
                  command_id, target_asset_id, command_type, issuer_id, box_id,
                  context_id, capability_id, purpose, parameters, status,
                  high_impact, issued_at, expires_at, approved_by,
                  approval_capability_id, approval_reason, approved_at,
                  dispatched_at, completed_at, result, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                on conflict (command_id) do update set
                  status = excluded.status,
                  approved_by = excluded.approved_by,
                  approval_capability_id = excluded.approval_capability_id,
                  approval_reason = excluded.approval_reason,
                  approved_at = excluded.approved_at,
                  dispatched_at = excluded.dispatched_at,
                  completed_at = excluded.completed_at,
                  result = excluded.result,
                  updated_at = excluded.updated_at
                """,
                (
                    command.command_id,
                    command.target_asset_id,
                    command.command_type,
                    command.issuer_id,
                    command.box_id,
                    command.context_id,
                    command.capability_id,
                    command.purpose,
                    json.dumps(command.parameters),
                    command.status,
                    command.high_impact,
                    command.issued_at,
                    command.expires_at,
                    command.approved_by,
                    command.approval_capability_id,
                    command.approval_reason,
                    command.approved_at,
                    command.dispatched_at,
                    command.completed_at,
                    json.dumps(command.result) if command.result is not None else None,
                    command.updated_at,
                ),
            )
        return command

    def list_commands(self) -> list[FleetCommand]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select command_id, target_asset_id, command_type, issuer_id,
                       box_id, context_id, capability_id, purpose, parameters,
                       status, high_impact, issued_at, expires_at, approved_by,
                       approval_capability_id, approval_reason, approved_at,
                       dispatched_at, completed_at, result, updated_at
                from genesis_control_tower.fleet_commands order by issued_at, command_id
                """,
            )
        return [
            FleetCommand.model_validate(_decode_fields(row, "parameters", "result"))
            for row in rows
        ]
