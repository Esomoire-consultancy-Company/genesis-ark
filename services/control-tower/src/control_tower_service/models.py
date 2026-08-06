from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ResourceIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^(?:\*|[A-Za-z0-9][A-Za-z0-9._:/-]*)$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FleetAssetType(StrEnum):
    RUNTIME_NODE = "RUNTIME_NODE"
    EDGE_NODE = "EDGE_NODE"
    RUNTIME_INSTANCE = "RUNTIME_INSTANCE"
    ACTOR_BOX = "ACTOR_BOX"
    CLOUDBROWSER_SESSION = "CLOUDBROWSER_SESSION"
    AGENT = "AGENT"
    DEVICE = "DEVICE"
    VEHICLE = "VEHICLE"
    MERCHANT_TERMINAL = "MERCHANT_TERMINAL"


class FleetStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DRAINING = "DRAINING"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class IncidentSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_RANK = {
    IncidentSeverity.LOW: 1,
    IncidentSeverity.MEDIUM: 2,
    IncidentSeverity.HIGH: 3,
    IncidentSeverity.CRITICAL: 4,
}


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class FleetCommandType(StrEnum):
    RUN_DIAGNOSTICS = "RUN_DIAGNOSTICS"
    COLLECT_LOGS = "COLLECT_LOGS"
    RESTART_RUNTIME = "RESTART_RUNTIME"
    DRAIN_NODE = "DRAIN_NODE"
    PAUSE_RUNTIME = "PAUSE_RUNTIME"
    SUSPEND_NODE = "SUSPEND_NODE"
    ROTATE_CERTIFICATE = "ROTATE_CERTIFICATE"
    LOCK_ACTOR_BOX = "LOCK_ACTOR_BOX"
    UPGRADE_RUNTIME = "UPGRADE_RUNTIME"


HIGH_IMPACT_COMMANDS = {
    FleetCommandType.RESTART_RUNTIME,
    FleetCommandType.DRAIN_NODE,
    FleetCommandType.PAUSE_RUNTIME,
    FleetCommandType.SUSPEND_NODE,
    FleetCommandType.ROTATE_CERTIFICATE,
    FleetCommandType.LOCK_ACTOR_BOX,
    FleetCommandType.UPGRADE_RUNTIME,
}


class CommandStatus(StrEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class CommandCompletionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CapabilityAuthorization(StrictModel):
    capability_id: Identifier
    box_id: Identifier
    subject_id: Identifier
    context_id: Identifier
    resource_id: ResourceIdentifier
    allowed_action: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    expires_at: datetime
    constraints: dict[str, Any] = Field(default_factory=dict)


class UpsertFleetAssetRequest(StrictModel):
    asset_id: Identifier
    asset_type: FleetAssetType
    anchor_id: Identifier
    authority_reference: Identifier
    owner_reference: Identifier
    region: str = Field(min_length=1, max_length=100)
    jurisdiction: str = Field(min_length=1, max_length=100)
    status: FleetStatus
    health_score: int = Field(ge=0, le=100)
    attestation_reference: Identifier | None = None
    policy_version: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class FleetAsset(UpsertFleetAssetRequest):
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "FleetAsset":
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


class ReportSignalRequest(StrictModel):
    signal_id: Identifier
    subject_asset_id: Identifier
    signal_type: str = Field(min_length=1, max_length=120)
    severity: IncidentSeverity
    summary: str = Field(min_length=1, max_length=500)
    fingerprint: str | None = Field(default=None, min_length=8, max_length=200)
    source_reference: Identifier
    observed_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class Incident(StrictModel):
    incident_id: Identifier
    fingerprint: str
    subject_asset_id: Identifier
    signal_type: str
    severity: IncidentSeverity
    status: IncidentStatus
    summary: str
    occurrence_count: int = Field(ge=1)
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_by: Identifier | None = None
    acknowledged_at: datetime | None = None
    resolved_by: Identifier | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None
    created_at: datetime
    updated_at: datetime


class IncidentActionRequest(StrictModel):
    actor_id: Identifier
    box_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    purpose: str = Field(min_length=1, max_length=300)
    note: str = Field(min_length=1, max_length=1000)


class CreateFleetCommandRequest(StrictModel):
    command_id: Identifier
    target_asset_id: Identifier
    command_type: FleetCommandType
    issuer_id: Identifier
    box_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    purpose: str = Field(min_length=1, max_length=300)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_ttl_seconds: int = Field(ge=1, le=3600)


class FleetCommand(StrictModel):
    command_id: Identifier
    target_asset_id: Identifier
    command_type: FleetCommandType
    issuer_id: Identifier
    box_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    purpose: str
    parameters: dict[str, Any]
    status: CommandStatus
    high_impact: bool
    issued_at: datetime
    expires_at: datetime
    approved_by: Identifier | None = None
    approval_capability_id: Identifier | None = None
    approval_reason: str | None = None
    approved_at: datetime | None = None
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "FleetCommand":
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        if self.updated_at < self.issued_at:
            raise ValueError("updated_at cannot precede issued_at")
        return self


class ApproveFleetCommandRequest(StrictModel):
    approver_id: Identifier
    box_id: Identifier
    context_id: Identifier
    approval_capability_id: Identifier
    purpose: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=1000)


class DispatchFleetCommandRequest(StrictModel):
    actor_id: Identifier
    box_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    purpose: str = Field(min_length=1, max_length=300)


class CompleteFleetCommandRequest(StrictModel):
    status: CommandCompletionStatus
    completed_by: Identifier
    result: dict[str, Any] = Field(default_factory=dict)


class DashboardSnapshot(StrictModel):
    generated_at: datetime
    assets_by_status: dict[str, int]
    assets_by_type: dict[str, int]
    incidents_by_severity: dict[str, int]
    incidents_by_status: dict[str, int]
    commands_by_status: dict[str, int]
    total_assets: int = Field(ge=0)
    open_incidents: int = Field(ge=0)
    pending_authorizations: int = Field(ge=0)


class ControlTowerEvent(StrictModel):
    event_id: Identifier
    aggregate_type: str
    aggregate_id: Identifier
    subject_id: Identifier
    event_type: str
    actor_id: Identifier
    payload: dict[str, Any]
    occurred_at: datetime
    previous_event_hash: HexDigest | None = None
    evidence_hash: HexDigest
    published_at: datetime | None = None
