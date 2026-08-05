from __future__ import annotations

import json
from typing import Any

from .models import ControlCommandRequest, ControlIncident, DispatchedEdgeCommand


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class PostgresOperationsMixin:
    @staticmethod
    def _command(row: Any | None) -> ControlCommandRequest | None:
        if row is None:
            return None
        data = dict(row)
        data["payload"] = _json(data["payload"])
        return ControlCommandRequest.model_validate(data)

    def get_command_request(self, request_id: str) -> ControlCommandRequest | None:
        with self._connection() as connection:
            row = self._one(connection, "select * from genesis_control_tower.command_requests where request_id = %s", (request_id,))
        return self._command(row)

    def save_command_request(self, request: ControlCommandRequest) -> ControlCommandRequest:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_control_tower.command_requests (
                  request_id, node_id, command_type, required_capability_action,
                  requested_by, target_reference, payload, purpose, status,
                  expires_at, authorization_capability_id, authorized_by,
                  authorized_at, authorization_reason, dispatched_command_id,
                  dispatched_at, rejection_reason, created_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (request_id) do update set
                  status = excluded.status,
                  authorization_capability_id = excluded.authorization_capability_id,
                  authorized_by = excluded.authorized_by,
                  authorized_at = excluded.authorized_at,
                  authorization_reason = excluded.authorization_reason,
                  dispatched_command_id = excluded.dispatched_command_id,
                  dispatched_at = excluded.dispatched_at,
                  rejection_reason = excluded.rejection_reason,
                  updated_at = excluded.updated_at
                """,
                (
                    request.request_id,
                    request.node_id,
                    request.command_type.value,
                    request.required_capability_action,
                    request.requested_by,
                    request.target_reference,
                    json.dumps(request.payload),
                    request.purpose,
                    request.status.value,
                    request.expires_at,
                    request.authorization_capability_id,
                    request.authorized_by,
                    request.authorized_at,
                    request.authorization_reason,
                    request.dispatched_command_id,
                    request.dispatched_at,
                    request.rejection_reason,
                    request.created_at,
                    request.updated_at,
                ),
            )
        return request

    def list_command_requests(self) -> list[ControlCommandRequest]:
        with self._connection() as connection:
            rows = self._all(connection, "select * from genesis_control_tower.command_requests order by created_at, request_id")
        return [item for row in rows if (item := self._command(row)) is not None]

    def dispatch_command(self, request: ControlCommandRequest, command: DispatchedEdgeCommand) -> None:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_edge.edge_commands (
                  command_id, node_id, command_type, capability_id,
                  required_capability_action, issued_by, target_reference,
                  payload, status, attempts, issued_at, expires_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'PENDING',0,%s,%s,%s)
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
                    command.issued_at,
                    command.expires_at,
                    command.issued_at,
                ),
            )
            self.save_command_request(request)

    @staticmethod
    def _incident(row: Any | None) -> ControlIncident | None:
        if row is None:
            return None
        data = dict(row)
        data["evidence_references"] = _json(data["evidence_references"])
        return ControlIncident.model_validate(data)

    def get_incident(self, incident_id: str) -> ControlIncident | None:
        with self._connection() as connection:
            row = self._one(connection, "select * from genesis_control_tower.incidents where incident_id = %s", (incident_id,))
        return self._incident(row)

    def save_incident(self, incident: ControlIncident) -> ControlIncident:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_control_tower.incidents (
                  incident_id, node_id, severity, incident_type, summary, source,
                  status, opened_by, assigned_to, evidence_references,
                  resolution_note, opened_at, acknowledged_at, mitigating_at,
                  resolved_at, closed_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
                on conflict (incident_id) do update set
                  severity = excluded.severity,
                  summary = excluded.summary,
                  status = excluded.status,
                  assigned_to = excluded.assigned_to,
                  evidence_references = excluded.evidence_references,
                  resolution_note = excluded.resolution_note,
                  acknowledged_at = excluded.acknowledged_at,
                  mitigating_at = excluded.mitigating_at,
                  resolved_at = excluded.resolved_at,
                  closed_at = excluded.closed_at,
                  updated_at = excluded.updated_at
                """,
                (
                    incident.incident_id,
                    incident.node_id,
                    incident.severity.value,
                    incident.incident_type,
                    incident.summary,
                    incident.source.value,
                    incident.status.value,
                    incident.opened_by,
                    incident.assigned_to,
                    json.dumps(incident.evidence_references),
                    incident.resolution_note,
                    incident.opened_at,
                    incident.acknowledged_at,
                    incident.mitigating_at,
                    incident.resolved_at,
                    incident.closed_at,
                    incident.updated_at,
                ),
            )
        return incident

    def list_incidents(self) -> list[ControlIncident]:
        with self._connection() as connection:
            rows = self._all(connection, "select * from genesis_control_tower.incidents order by opened_at, incident_id")
        return [item for row in rows if (item := self._incident(row)) is not None]

    def find_open_incident(self, node_id: str, incident_type: str) -> ControlIncident | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                """
                select * from genesis_control_tower.incidents
                where node_id = %s and incident_type = %s
                  and status in ('OPEN', 'ACKNOWLEDGED', 'MITIGATING')
                order by opened_at, incident_id limit 1
                """,
                (node_id, incident_type),
            )
        return self._incident(row)
