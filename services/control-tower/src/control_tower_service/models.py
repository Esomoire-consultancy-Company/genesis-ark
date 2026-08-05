from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FleetStatus(StrEnum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    QUARANTINED = "QUARANTINED"
    DRAINING = "DRAINING"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class CommandType(StrEnum):
    START_INSTANCE = "START_INSTANCE"
    STOP_INSTANCE = "STOP_INSTANCE"
    PAUSE_SESSION = "PAUSE_SESSION"
    TERMINATE_SESSION = "TERMINATE_SESSION"
    EXECUTE_RECOVERY = "EXECUTE_RECOVERY"
    ROTATE_AGENT = "ROTATE_AGENT"
    DRAIN_NODE = "DRAIN_NODE"


class CommandRequestStatus(StrEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    DISPATCHED = "DISPATCHED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AuthorizationDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class IncidentSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentSource(StrEnum):
    SYSTEM = "SYSTEM"
    MANUAL = "MANUAL"


class PublicationStream(StrEnum):
    RUNTIME = "RUNTIME"
    EDGE = "EDGE"
    CONTROL_TOWER = "CONTROL_TOWER"


class PublicationLeaseStatus(StrEnum):
    LEASED = "LEASED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class SourceFleetObservation(StrictModel):
    node_id: Identifier
    node_class: str = Field(min_length=1)
    region: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    runtime_status: str = Field(min_length=1)
    edge_status: str | None = None
    last_seen_at: datetime | None = None
    capacity: dict[str, int] = Field(default_factory=dict)
    active_instances: int = Field(default=0, ge=0)
    active_sessions: int = Field(default=0, ge=0)
    pending_commands: int = Field(default=0, ge=0)
    latest_metrics: dict[str, float] = Field(default_factory=dict)


class FleetNodeSnapshot(StrictModel):
    node_id: Identifier
    node_class: str
    region: str
    jurisdiction: str
    runtime_status: str
    edge_status: str | None = None
    effective_status: FleetStatus
    last_seen_at: datetime | None = None
    heartbeat_age_seconds: int | None = Field(default=None, ge=0)
    active_instances: int = Field(ge=0)
    active_sessions: int = Field(ge=0)
    pending_commands: int = Field(ge=0)
    open_incidents: int = Field(ge=0)
    capacity: dict[str, int]
    latest_metrics: dict[str, float]
    source_fingerprint: HexDigest
    observed_at: datetime


class FleetRefreshRequest(StrictModel):
    actor_id: Identifier


class FleetRefreshReceipt(StrictModel):
    observed_at: datetime
    refreshed_node_ids: list[Identifier]
    opened_incident_ids: list[Identifier]
    resolved_incident_ids: list[Identifier]
    evidence_event_id: Identifier


class CreateCommandRequest(StrictModel):
    request_id: Identifier
    node_id: Identifier
    command_type: CommandType
    requested_by: Identifier
    target_reference: Identifier
    payload: dict[str, Any] = Field(default_factory=dict)
    purpose: str = Field(min_length=1)
    expires_at: datetime


class ControlCommandRequest(StrictModel):
    request_id: Identifier
    node_id: Identifier
    command_type: CommandType
    required_capability_action: str
    requested_by: Identifier
    target_reference: Identifier
    payload: dict[str, Any]
    purpose: str
    status: CommandRequestStatus
    expires_at: datetime
    authorization_capability_id: Identifier | None = None
    authorized_by: Identifier | None = None
    authorized_at: datetime | None = None
    authorization_reason: str | None = None
    dispatched_command_id: Identifier | None = None
    dispatched_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "ControlCommandRequest":
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


class AuthorizeCommandRequest(StrictModel):
    decision: AuthorizationDecision
    actor_id: Identifier
    reason: str = Field(min_length=1)
    capability_id: Identifier | None = None

    @model_validator(mode="after")
    def approval_requires_capability(self) -> "AuthorizeCommandRequest":
        if self.decision == AuthorizationDecision.APPROVE and self.capability_id is None:
            raise ValueError("capability_id is required for approval")
        return self


class DispatchCommandRequest(StrictModel):
    actor_id: Identifier


class DispatchedEdgeCommand(StrictModel):
    command_id: Identifier
    node_id: Identifier
    command_type: CommandType
    capability_id: Identifier
    required_capability_action: str
    issued_by: Identifier
    target_reference: Identifier
    payload: dict[str, Any]
    issued_at: datetime
    expires_at: datetime


class CreateIncidentRequest(StrictModel):
    incident_id: Identifier
    node_id: Identifier
    severity: IncidentSeverity
    incident_type: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    opened_by: Identifier
    evidence_references: list[Identifier] = Field(default_factory=list)


class IncidentTransitionRequest(StrictModel):
    status: IncidentStatus
    actor_id: Identifier
    note: str = Field(min_length=1)


class ControlIncident(StrictModel):
    incident_id: Identifier
    node_id: Identifier
    severity: IncidentSeverity
    incident_type: str
    summary: str
    source: IncidentSource
    status: IncidentStatus
    opened_by: Identifier
    assigned_to: Identifier | None = None
    evidence_references: list[Identifier]
    resolution_note: str | None = None
    opened_at: datetime
    acknowledged_at: datetime | None = None
    mitigating_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime


class PublicationSourceEvent(StrictModel):
    stream: PublicationStream
    event_id: Identifier
    aggregate_id: Identifier
    event_type: str = Field(min_length=1)
    evidence_hash: HexDigest
    payload: dict[str, Any]
    occurred_at: datetime


class PublicationLeaseRequest(StrictModel):
    publisher_id: Identifier
    max_events: int = Field(default=50, ge=1, le=100)
    lease_seconds: int | None = Field(default=None, ge=1, le=3600)


class PublicationLease(StrictModel):
    lease_id: Identifier
    publisher_id: Identifier
    lease_token: str = Field(min_length=32)
    status: PublicationLeaseStatus
    events: list[PublicationSourceEvent]
    leased_at: datetime
    expires_at: datetime


class PublicationAckItem(StrictModel):
    stream: PublicationStream
    event_id: Identifier
    destination_reference: Identifier


class PublicationAckRequest(StrictModel):
    publisher_id: Identifier
    lease_token: str = Field(min_length=32)
    items: list[PublicationAckItem] = Field(min_length=1)


class PublicationReceipt(StrictModel):
    lease_id: Identifier
    acknowledged_event_ids: list[Identifier]
    acknowledged_at: datetime


class DashboardSummary(StrictModel):
    generated_at: datetime
    total_nodes: int = Field(ge=0)
    nodes_by_status: dict[FleetStatus, int]
    open_incidents: int = Field(ge=0)
    critical_incidents: int = Field(ge=0)
    authorization_queue: int = Field(ge=0)
    authorized_commands: int = Field(ge=0)
    unpublished_evidence: int = Field(ge=0)


class CapabilityGrant(StrictModel):
    capability_id: Identifier
    subject_id: Identifier
    resource_id: Identifier
    allowed_action: str
    expires_at: datetime


class ControlTowerEvent(StrictModel):
    event_id: Identifier
    aggregate_type: str
    aggregate_id: Identifier
    event_type: str
    actor_id: Identifier
    payload: dict[str, Any]
    occurred_at: datetime
    previous_event_hash: HexDigest | None = None
    evidence_hash: HexDigest
