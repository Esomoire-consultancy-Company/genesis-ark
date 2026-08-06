from __future__ import annotations

from datetime import timedelta
import hashlib
import json

from .capabilities import CapabilityVerifier
from .config import Settings
from .errors import ForbiddenError, NotFoundError, StateConflictError
from .evidence import build_event, new_id, utcnow
from .models import (
    ApproveFleetCommandRequest, CommandCompletionStatus, CommandStatus,
    CompleteFleetCommandRequest, CreateFleetCommandRequest, DashboardSnapshot,
    DispatchFleetCommandRequest, FleetAsset, FleetCommand, HIGH_IMPACT_COMMANDS,
    Incident, IncidentActionRequest, IncidentStatus, ReportSignalRequest,
    SEVERITY_RANK, UpsertFleetAssetRequest,
)
from .repository import ControlTowerRepository

class ControlTowerBase:
    def __init__(
        self,
        repository: ControlTowerRepository,
        capability_verifier: CapabilityVerifier,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.capability_verifier = capability_verifier
        self.settings = settings

    def dashboard(self) -> DashboardSnapshot:
        assets = self.repository.list_assets()
        incidents = self.repository.list_incidents()
        commands = self.repository.list_commands()
        return DashboardSnapshot(
            generated_at=utcnow(),
            assets_by_status=self._counts(item.status for item in assets),
            assets_by_type=self._counts(item.asset_type for item in assets),
            incidents_by_severity=self._counts(item.severity for item in incidents),
            incidents_by_status=self._counts(item.status for item in incidents),
            commands_by_status=self._counts(item.status for item in commands),
            total_assets=len(assets),
            open_incidents=sum(item.status != IncidentStatus.RESOLVED for item in incidents),
            pending_authorizations=sum(
                item.status == CommandStatus.AUTHORIZATION_REQUIRED for item in commands
            ),
        )

    def audit(self, subject_id: str):
        return self.repository.list_events_for_subject(subject_id)

    @staticmethod
    def _counts(values) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _incident(self, incident_id: str) -> Incident:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise NotFoundError(
                "Incident was not found",
                reason_codes=["INCIDENT_NOT_FOUND"],
            )
        return incident

    def _command(self, command_id: str) -> FleetCommand:
        command = self.repository.get_command(command_id)
        if command is None:
            raise NotFoundError(
                "Fleet command was not found",
                reason_codes=["COMMAND_NOT_FOUND"],
            )
        return command

    @staticmethod
    def _assert_command_not_expired(command: FleetCommand, at) -> None:
        if command.expires_at <= at:
            raise StateConflictError(
                "Fleet command has expired",
                reason_codes=["COMMAND_EXPIRED"],
            )

    def _require_capability(
        self,
        *,
        capability_id: str,
        box_id: str,
        principal_id: str,
        context_id: str,
        resource_id: str,
        action: str,
        purpose: str,
        at,
    ):
        authorization = self.capability_verifier.verify(
            capability_id=capability_id,
            box_id=box_id,
            principal_id=principal_id,
            context_id=context_id,
            resource_id=resource_id,
            required_actions={action},
            purpose=purpose,
            at=at,
        )
        if authorization is None:
            raise ForbiddenError(
                "No active Warden capability authorizes this Control Tower action",
                reason_codes=["CAPABILITY_NOT_ACTIVE"],
            )
        return authorization

    def _emit(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        subject_id: str,
        event_type: str,
        actor_id: str,
        payload: dict,
    ) -> None:
        latest = self.repository.latest_event(aggregate_type, aggregate_id)
        event = build_event(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            subject_id=subject_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
            previous_event_hash=latest.evidence_hash if latest else None,
        )
        self.repository.append_event(event)
