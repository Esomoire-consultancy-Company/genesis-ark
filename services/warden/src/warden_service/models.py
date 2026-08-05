from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoxStatus(StrEnum):
    RESERVED = "RESERVED"
    PROVISIONED = "PROVISIONED"
    CLAIM_PENDING = "CLAIM_PENDING"
    CLAIMED = "CLAIMED"
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    SUSPENDED = "SUSPENDED"
    RECOVERY = "RECOVERY"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    COMPROMISED = "COMPROMISED"
    REVOKED = "REVOKED"
    RETIREMENT_PENDING = "RETIREMENT_PENDING"
    RETIRED = "RETIRED"


class RuntimeIntegrity(StrEnum):
    ATTESTED = "ATTESTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ControlStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class DecisionOutcome(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    RESTRICT = "RESTRICT"
    ESCALATE = "ESCALATE"


class CapabilityStatus(StrEnum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"


class PolicyDecisionRequest(StrictModel):
    request_id: Identifier
    requested_at: datetime
    box_id: Identifier
    runtime_id: Identifier
    subject_id: Identifier
    agent_id: Identifier | None = None
    context_id: Identifier
    resource_id: Identifier
    requested_action: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    data_classes: list[str]
    source_zone: str | None = None
    destination_zone: str | None = None
    requested_duration_seconds: int = Field(ge=1, le=3600)
    human_approval_present: bool


class CapabilityGrant(StrictModel):
    capability_id: Identifier
    box_id: Identifier
    subject_id: Identifier
    resource_id: Identifier
    allowed_action: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    context_id: Identifier
    issued_at: datetime
    expires_at: datetime
    policy_decision_id: Identifier
    capability_status: CapabilityStatus
    constraints: dict[str, Any]


class PolicyDecision(StrictModel):
    policy_decision_id: Identifier
    request_id: Identifier
    decided_at: datetime
    outcome: DecisionOutcome
    reason_codes: list[str] = Field(min_length=1)
    policy_bundle_version: str = Field(min_length=1)
    capability: CapabilityGrant | None = None
    required_approval: str | None = None
    evidence_event_id: Identifier


class CapabilityIssueRequest(StrictModel):
    policy_decision_id: Identifier
    requested_by: Identifier


class RevocationRequest(StrictModel):
    reason: str = Field(min_length=1)
    revoked_by: Identifier
    policy_reference: Identifier


class Revocation(StrictModel):
    revocation_id: Identifier
    box_id: Identifier
    target_type: str
    target_id: Identifier
    reason: str
    revoked_by: Identifier
    effective_at: datetime
    policy_reference: Identifier
    evidence_event_id: Identifier


class BoxLockRequest(StrictModel):
    reason: str = Field(min_length=1)
    initiated_by: Identifier
    policy_reference: Identifier


class BoxControlState(StrictModel):
    box_id: Identifier
    status: BoxStatus
    runtime_integrity: RuntimeIntegrity
    active_context_id: Identifier
    active_capability_count: int = Field(ge=0)
    active_agent_count: int = Field(ge=0)
    locked: bool
    updated_at: datetime
    evidence_event_id: Identifier


class ActorBoxRecord(StrictModel):
    box_id: Identifier
    status: BoxStatus
    policy_profile_id: Identifier
    evidence_stream_id: Identifier
    locked: bool = False
    updated_at: datetime


class RuntimeRecord(StrictModel):
    runtime_id: Identifier
    box_id: Identifier
    integrity_status: RuntimeIntegrity
    last_attested_at: datetime


class BindingRecord(StrictModel):
    binding_id: Identifier
    box_id: Identifier
    digitalme_id: Identifier
    status: ControlStatus
    effective_from: datetime
    effective_until: datetime | None = None


class ContextRecord(StrictModel):
    context_id: Identifier
    box_id: Identifier
    principal_id: Identifier
    workspace_id: Identifier
    status: ControlStatus
    activated_at: datetime
    expires_at: datetime | None = None


class PolicyProfileRecord(StrictModel):
    policy_profile_id: Identifier
    box_id: Identifier
    policy_bundle_version: str
    status: ControlStatus
    effective_from: datetime
    effective_until: datetime | None = None
    max_capability_ttl_seconds: int = Field(default=1200, ge=1, le=3600)


class ConsentRecord(StrictModel):
    consent_receipt_id: Identifier
    box_id: Identifier
    digitalme_id: Identifier
    purpose: str
    data_scope: list[str]
    action_scope: list[str]
    status: ControlStatus
    effective_from: datetime
    effective_until: datetime | None = None


class DelegationRecord(StrictModel):
    delegation_id: Identifier
    box_id: Identifier
    agent_id: Identifier
    delegating_principal_id: Identifier
    permitted_actions: list[str]
    permitted_data_scope: list[str]
    workspace_scope: list[str]
    status: ControlStatus
    effective_from: datetime
    effective_until: datetime | None = None
    write_requires_human_approval: bool = True


class BoundaryRuleRecord(StrictModel):
    boundary_rule_id: Identifier
    box_id: Identifier
    source_zone: str
    destination_zone: str
    data_class: str
    permitted_purpose: str
    status: ControlStatus
    effective_from: datetime
    effective_until: datetime | None = None


class DecisionRecord(StrictModel):
    decision: PolicyDecision
    request: PolicyDecisionRequest


class EvidenceEvent(StrictModel):
    event_id: Identifier
    box_id: Identifier
    event_type: str
    actor_id: Identifier
    agent_id: Identifier | None = None
    context_id: Identifier | None = None
    action_reference: str
    policy_decision: str
    timestamp: datetime
    payload: dict[str, Any]
    previous_event_hash: str | None = None
    evidence_hash: str
