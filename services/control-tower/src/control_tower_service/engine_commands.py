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

class CommandOperations:
    def create_command(self, request: CreateFleetCommandRequest) -> FleetCommand:
        now = utcnow()
        target = self.get_asset(request.target_asset_id)
        with self.repository.transaction(f"command:{request.command_id}"):
            existing = self.repository.get_command(request.command_id)
            if existing is not None:
                comparable = {
                    "command_id": existing.command_id,
                    "target_asset_id": existing.target_asset_id,
                    "command_type": existing.command_type,
                    "issuer_id": existing.issuer_id,
                    "box_id": existing.box_id,
                    "context_id": existing.context_id,
                    "capability_id": existing.capability_id,
                    "purpose": existing.purpose,
                    "parameters": existing.parameters,
                }
                requested = request.model_dump(exclude={"requested_ttl_seconds"})
                if comparable != requested:
                    raise StateConflictError(
                        "Fleet command ID was reused with different content",
                        reason_codes=["COMMAND_ID_CONFLICT"],
                    )
                return existing
            self._require_capability(
                capability_id=request.capability_id,
                box_id=request.box_id,
                principal_id=request.issuer_id,
                context_id=request.context_id,
                resource_id=request.target_asset_id,
                action="CONTROL_TOWER_COMMAND_ISSUE",
                purpose=request.purpose,
                at=now,
            )
            ttl = min(
                request.requested_ttl_seconds,
                self.settings.max_command_ttl_seconds,
            )
            high_impact = request.command_type in HIGH_IMPACT_COMMANDS
            command = FleetCommand(
                **request.model_dump(exclude={"requested_ttl_seconds"}),
                status=(
                    CommandStatus.AUTHORIZATION_REQUIRED
                    if high_impact
                    else CommandStatus.APPROVED
                ),
                high_impact=high_impact,
                issued_at=now,
                expires_at=now + timedelta(seconds=ttl),
                updated_at=now,
            )
            self.repository.save_command(command)
            self._emit(
                aggregate_type="COMMAND",
                aggregate_id=command.command_id,
                subject_id=target.asset_id,
                event_type=(
                    "COMMAND_AUTHORIZATION_REQUIRED"
                    if high_impact
                    else "COMMAND_APPROVED"
                ),
                actor_id=request.issuer_id,
                payload=command.model_dump(mode="json"),
            )
            return command

    def approve_command(
        self,
        command_id: str,
        request: ApproveFleetCommandRequest,
    ) -> FleetCommand:
        now = utcnow()
        with self.repository.transaction(f"command:{command_id}"):
            command = self._command(command_id)
            self._assert_command_not_expired(command, now)
            if not command.high_impact:
                return command
            if command.status == CommandStatus.APPROVED:
                return command
            if command.status != CommandStatus.AUTHORIZATION_REQUIRED:
                raise StateConflictError(
                    "Command cannot be approved in its current state",
                    reason_codes=[f"COMMAND_{command.status}"],
                )
            if request.approver_id == command.issuer_id:
                raise ForbiddenError(
                    "High-impact commands require an independent approver",
                    reason_codes=["FOUR_EYES_REQUIRED"],
                )
            self._require_capability(
                capability_id=request.approval_capability_id,
                box_id=request.box_id,
                principal_id=request.approver_id,
                context_id=request.context_id,
                resource_id=command_id,
                action="CONTROL_TOWER_COMMAND_APPROVE",
                purpose=request.purpose,
                at=now,
            )
            updated = command.model_copy(
                update={
                    "status": CommandStatus.APPROVED,
                    "approved_by": request.approver_id,
                    "approval_capability_id": request.approval_capability_id,
                    "approval_reason": request.reason,
                    "approved_at": now,
                    "updated_at": now,
                }
            )
            self.repository.save_command(updated)
            self._emit(
                aggregate_type="COMMAND",
                aggregate_id=command_id,
                subject_id=command.target_asset_id,
                event_type="COMMAND_APPROVED",
                actor_id=request.approver_id,
                payload={"reason": request.reason},
            )
            return updated

    def dispatch_command(
        self,
        command_id: str,
        request: DispatchFleetCommandRequest,
    ) -> FleetCommand:
        now = utcnow()
        with self.repository.transaction(f"command:{command_id}"):
            command = self._command(command_id)
            self._assert_command_not_expired(command, now)
            if command.status == CommandStatus.DISPATCHED:
                return command
            if command.status != CommandStatus.APPROVED:
                raise StateConflictError(
                    "Command has not been approved for dispatch",
                    reason_codes=[f"COMMAND_{command.status}"],
                )
            self._require_capability(
                capability_id=request.capability_id,
                box_id=request.box_id,
                principal_id=request.actor_id,
                context_id=request.context_id,
                resource_id=command_id,
                action="CONTROL_TOWER_COMMAND_DISPATCH",
                purpose=request.purpose,
                at=now,
            )
            updated = command.model_copy(
                update={
                    "status": CommandStatus.DISPATCHED,
                    "dispatched_at": now,
                    "updated_at": now,
                }
            )
            self.repository.save_command(updated)
            self._emit(
                aggregate_type="COMMAND",
                aggregate_id=command_id,
                subject_id=command.target_asset_id,
                event_type="EDGE_COMMAND_REQUESTED",
                actor_id=request.actor_id,
                payload={
                    "command_id": command.command_id,
                    "target_asset_id": command.target_asset_id,
                    "command_type": command.command_type,
                    "parameters": command.parameters,
                    "expires_at": command.expires_at.isoformat(),
                },
            )
            return updated

    def complete_command(
        self,
        command_id: str,
        request: CompleteFleetCommandRequest,
    ) -> FleetCommand:
        now = utcnow()
        with self.repository.transaction(f"command:{command_id}"):
            command = self._command(command_id)
            if command.status in {CommandStatus.COMPLETED, CommandStatus.FAILED}:
                return command
            if command.status != CommandStatus.DISPATCHED:
                raise StateConflictError(
                    "Only dispatched commands may be completed",
                    reason_codes=[f"COMMAND_{command.status}"],
                )
            status = (
                CommandStatus.COMPLETED
                if request.status == CommandCompletionStatus.COMPLETED
                else CommandStatus.FAILED
            )
            updated = command.model_copy(
                update={
                    "status": status,
                    "completed_at": now,
                    "result": request.result,
                    "updated_at": now,
                }
            )
            self.repository.save_command(updated)
            self._emit(
                aggregate_type="COMMAND",
                aggregate_id=command_id,
                subject_id=command.target_asset_id,
                event_type=f"COMMAND_{status}",
                actor_id=request.completed_by,
                payload=request.result,
            )
            return updated

    def list_commands(self) -> list[FleetCommand]:
        return self.repository.list_commands()
