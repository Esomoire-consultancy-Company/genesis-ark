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


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EdgeNodeStatus(StrEnum):
    ENROLLED = "ENROLLED"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DRAINING = "DRAINING"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


class CommandType(StrEnum):
    START_INSTANCE = "START_INSTANCE"
    STOP_INSTANCE = "STOP_INSTANCE"
    PAUSE_SESSION = "PAUSE_SESSION"
    TERMINATE_SESSION = "TERMINATE_SESSION"
    EXECUTE_RECOVERY = "EXECUTE_RECOVERY"
    ROTATE_AGENT = "ROTATE_AGENT"
    DRAIN_NODE = "DRAIN_NODE"


class CommandStatus(StrEnum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class CompletionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class EnrollNodeRequest(StrictModel):
    node_id: Identifier
    device_id: Identifier
    agent_id: Identifier
    hardware_fingerprint: HexDigest
    agent_version: str = Field(min_length=1, max_length=100)
    bootstrap_token: str = Field(min_length=16, max_length=512)
    credential_reference: Identifier
    attestation_reference: Identifier


class EdgeNodeIdentity(StrictModel):
    node_id: Identifier
    device_id: Identifier
    agent_id: Identifier
    hardware_fingerprint: HexDigest
    agent_version: str
    credential_reference: Identifier
    attestation_reference: Identifier
    status: EdgeNodeStatus
    last_heartbeat_sequence: int = Field(ge=0)
    last_spool_sequence: int = Field(default=0, ge=0)
    last_spool_hash: HexDigest | None = None
    last_seen_at: datetime | None = None
    enrolled_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "EdgeNodeIdentity":
        if self.last_seen_at is not None and self.last_seen_at < self.enrolled_at:
            raise ValueError("last_seen_at cannot precede enrolled_at")
        if self.updated_at < self.enrolled_at:
            raise ValueError("updated_at cannot precede enrolled_at")
        return self


class HeartbeatRequest(StrictModel):
    sequence: int = Field(ge=1)
    sent_at: datetime
    agent_version: str = Field(min_length=1, max_length=100)
    attestation_reference: Identifier
    runtime_digest: HexDigest
    node_state: EdgeNodeStatus
    metrics: dict[str, float] = Field(default_factory=dict)
    signature: HexDigest

    @field_validator("sent_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sent_at must include a timezone")
        return value


class HeartbeatReceipt(StrictModel):
    node_id: Identifier
    sequence: int = Field(ge=1)
    accepted_at: datetime
    node_status: EdgeNodeStatus
    evidence_event_id: Identifier


class IssueCommandRequest(StrictModel):
    command_id: Identifier
    command_type: CommandType
    capability_id: Identifier
    issued_by: Identifier
    target_reference: Identifier
    payload: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value


class EdgeCommand(StrictModel):
    command_id: Identifier
    node_id: Identifier
    command_type: CommandType
    capability_id: Identifier
    required_capability_action: str = Field(min_length=1)
    issued_by: Identifier
    target_reference: Identifier
    payload: dict[str, Any]
    status: CommandStatus
    attempts: int = Field(ge=0)
    issued_at: datetime
    expires_at: datetime
    lease_owner: Identifier | None = None
    lease_token_hash: HexDigest | None = None
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "EdgeCommand":
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        if self.status == CommandStatus.LEASED:
            if self.lease_owner is None or self.lease_token_hash is None or self.lease_expires_at is None:
                raise ValueError("LEASED commands require lease owner, token hash and expiry")
        if self.completed_at is not None and self.completed_at < self.issued_at:
            raise ValueError("completed_at cannot precede issued_at")
        if self.updated_at < self.issued_at:
            raise ValueError("updated_at cannot precede issued_at")
        return self


class LeaseCommandRequest(StrictModel):
    agent_id: Identifier
    lease_seconds: int | None = Field(default=None, ge=1, le=300)


class CommandLease(StrictModel):
    command: EdgeCommand
    lease_token: str = Field(min_length=32, max_length=512)


class CompleteCommandRequest(StrictModel):
    agent_id: Identifier
    lease_token: str = Field(min_length=32, max_length=512)
    status: CompletionStatus
    result: dict[str, Any] = Field(default_factory=dict)


class SpoolEvent(StrictModel):
    event_id: Identifier
    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=200)
    actor_id: Identifier
    occurred_at: datetime
    payload: dict[str, Any]
    previous_local_hash: HexDigest | None = None
    local_hash: HexDigest

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class SpoolFlushRequest(StrictModel):
    events: list[SpoolEvent] = Field(min_length=1, max_length=500)
    batch_signature: HexDigest

    @model_validator(mode="after")
    def require_contiguous_events(self) -> "SpoolFlushRequest":
        expected = self.events[0].sequence
        previous_hash: str | None = self.events[0].previous_local_hash
        seen_ids: set[str] = set()
        for event in self.events:
            if event.event_id in seen_ids:
                raise ValueError("spool event IDs must be unique within a batch")
            seen_ids.add(event.event_id)
            if event.sequence != expected:
                raise ValueError("spool event sequences must be contiguous")
            if event.previous_local_hash != previous_hash:
                raise ValueError("spool event local hash chain is not contiguous")
            previous_hash = event.local_hash
            expected += 1
        return self


class SpoolFlushReceipt(StrictModel):
    node_id: Identifier
    accepted_event_ids: list[Identifier]
    last_sequence: int = Field(ge=0)
    accepted_at: datetime


class EdgeEvidenceEvent(StrictModel):
    event_id: Identifier
    node_id: Identifier
    event_type: str = Field(min_length=1)
    actor_id: Identifier
    payload: dict[str, Any]
    occurred_at: datetime
    previous_event_hash: HexDigest | None = None
    evidence_hash: HexDigest
