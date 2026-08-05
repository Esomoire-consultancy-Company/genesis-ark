from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeStatus(StrEnum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


class InstanceStatus(StrEnum):
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    STOPPED = "STOPPED"
    RETIRED = "RETIRED"


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"
    EXPIRED = "EXPIRED"


class SessionType(StrEnum):
    ACTOR = "ACTOR"
    CLOUDBROWSER = "CLOUDBROWSER"
    AGENT = "AGENT"
    WORKSPACE = "WORKSPACE"
    MERCHANT = "MERCHANT"
    VEHICLE = "VEHICLE"


class IntegrityStatus(StrEnum):
    ATTESTED = "ATTESTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class AllocationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class RecoveryStatus(StrEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResourceVector(StrictModel):
    cpu_millis: int = Field(default=0, ge=0)
    memory_mb: int = Field(default=0, ge=0)
    gpu_millis: int = Field(default=0, ge=0)
    storage_mb: int = Field(default=0, ge=0)
    network_egress_mb: int = Field(default=0, ge=0)
    browser_slots: int = Field(default=0, ge=0)

    def plus(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(
            **{
                field: getattr(self, field) + getattr(other, field)
                for field in type(self).model_fields
            }
        )

    def fits_within(self, limit: "ResourceVector") -> bool:
        return all(
            getattr(self, field) <= getattr(limit, field)
            for field in type(self).model_fields
        )


class RegisterNodeRequest(StrictModel):
    node_id: Identifier
    node_class: str = Field(min_length=1)
    region: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    authority_reference: Identifier
    attestation_reference: Identifier
    capacity: ResourceVector


class RuntimeNode(StrictModel):
    node_id: Identifier
    node_class: str
    region: str
    jurisdiction: str
    authority_reference: Identifier
    attestation_reference: Identifier
    status: NodeStatus
    capacity: ResourceVector
    registered_at: datetime
    updated_at: datetime


class ProvisionInstanceRequest(StrictModel):
    instance_id: Identifier
    node_id: Identifier
    box_id: Identifier
    runtime_class: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    requested_by: Identifier
    authority_reference: Identifier
    resource_limits: ResourceVector


class RuntimeInstance(StrictModel):
    instance_id: Identifier
    node_id: Identifier
    box_id: Identifier
    runtime_class: str
    runtime_version: str
    status: InstanceStatus
    integrity_status: IntegrityStatus
    resource_limits: ResourceVector
    attestation_reference: Identifier | None = None
    provisioned_at: datetime
    activated_at: datetime | None = None
    last_attested_at: datetime | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def validate_lifecycle_times(self) -> "RuntimeInstance":
        for field_name in ("activated_at", "last_attested_at", "updated_at"):
            value = getattr(self, field_name)
            if value is not None and value < self.provisioned_at:
                raise ValueError(f"{field_name} cannot precede provisioned_at")
        if self.status == InstanceStatus.ACTIVE and self.integrity_status != IntegrityStatus.ATTESTED:
            raise ValueError("ACTIVE runtime instances must be ATTESTED")
        return self


class AttestInstanceRequest(StrictModel):
    integrity_status: IntegrityStatus
    attestation_reference: Identifier
    attested_by: Identifier


class CreateSessionRequest(StrictModel):
    session_id: Identifier
    instance_id: Identifier
    box_id: Identifier
    principal_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    session_type: SessionType
    purpose: str = Field(min_length=1)
    requested_duration_seconds: int = Field(ge=1, le=3600)


class RuntimeSession(StrictModel):
    session_id: Identifier
    instance_id: Identifier
    box_id: Identifier
    principal_id: Identifier
    context_id: Identifier
    capability_id: Identifier
    session_type: SessionType
    purpose: str
    status: SessionStatus
    started_at: datetime
    expires_at: datetime
    terminated_at: datetime | None = None
    termination_reason: str | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def validate_session_times(self) -> "RuntimeSession":
        if self.expires_at <= self.started_at:
            raise ValueError("expires_at must be later than started_at")
        if self.terminated_at is not None and self.terminated_at < self.started_at:
            raise ValueError("terminated_at cannot precede started_at")
        if self.updated_at < self.started_at:
            raise ValueError("updated_at cannot precede started_at")
        return self


class AllocateResourcesRequest(StrictModel):
    allocation_id: Identifier
    capability_id: Identifier
    resources: ResourceVector

    @model_validator(mode="after")
    def require_nonzero_request(self) -> "AllocateResourcesRequest":
        if not any(getattr(self.resources, field) > 0 for field in type(self.resources).model_fields):
            raise ValueError("at least one resource amount must be greater than zero")
        return self


class ResourceAllocation(StrictModel):
    allocation_id: Identifier
    session_id: Identifier
    capability_id: Identifier
    resources: ResourceVector
    status: AllocationStatus
    allocated_at: datetime
    released_at: datetime | None = None

    @model_validator(mode="after")
    def validate_allocation_times(self) -> "ResourceAllocation":
        if self.released_at is not None and self.released_at < self.allocated_at:
            raise ValueError("released_at cannot precede allocated_at")
        return self


class HealthReportRequest(StrictModel):
    state: HealthState
    reported_by: Identifier
    checks: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)


class RuntimeHealthReport(StrictModel):
    health_report_id: Identifier
    instance_id: Identifier
    state: HealthState
    reported_by: Identifier
    checks: dict[str, str]
    metrics: dict[str, float]
    reported_at: datetime


class RecoveryJob(StrictModel):
    recovery_job_id: Identifier
    instance_id: Identifier
    status: RecoveryStatus
    trigger_health_report_id: Identifier
    required_capability_action: str
    created_at: datetime
    authorized_at: datetime | None = None


class TerminateSessionRequest(StrictModel):
    reason: str = Field(min_length=1)
    initiated_by: Identifier


class RuntimeEvent(StrictModel):
    event_id: Identifier
    aggregate_type: str = Field(min_length=1)
    aggregate_id: Identifier
    box_id: Identifier | None = None
    event_type: str = Field(min_length=1)
    payload: dict[str, Any]
    occurred_at: datetime
    previous_event_hash: str | None = Field(default=None, min_length=64, max_length=64)
    evidence_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    published_at: datetime | None = None

    @field_validator("occurred_at", "published_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("runtime event timestamps must be timezone-aware")
        return value


class CapabilityAuthorization(StrictModel):
    capability_id: Identifier
    box_id: Identifier
    subject_id: Identifier
    context_id: Identifier
    resource_id: Identifier
    allowed_action: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    expires_at: datetime
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capability expiry must be timezone-aware")
        return value
