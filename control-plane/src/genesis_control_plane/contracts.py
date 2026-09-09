from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class DecisionResult(StrEnum):
    PERMIT = "PERMIT"
    DENY = "DENY"


class ExecutionState(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationState(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class Command:
    command_id: str
    correlation_id: str
    principal_id: str
    session_id: str
    station_id: str
    adapter_id: str
    target_resource_id: str
    capability: str
    parameters: Mapping[str, Any]
    risk_class: str
    environment: str
    requested_at: str
    expires_at: str


@dataclass(frozen=True)
class Decision:
    decision_id: str
    command_id: str
    result: DecisionResult
    policy_id: str
    conditions: tuple[str, ...]
    obligations: tuple[str, ...]
    decided_at: str
    valid_until: str
    reason_code: str


@dataclass(frozen=True)
class CapabilityTokenClaims:
    token_id: str
    decision_id: str
    command_id: str
    principal_id: str
    session_id: str
    station_id: str
    adapter_id: str
    target_resource_id: str
    capability: str
    parameters_hash: str
    audience: str
    issued_at: str
    not_before: str
    expires_at: str
    max_uses: int
    nonce: str
    key_id: str


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    command_id: str
    target_resource_id: str
    state: ExecutionState
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    completed_at: str


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    execution_id: str
    target_resource_id: str
    state: VerificationState
    observed_state: str
    verified_at: str


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    event_type: str
    schema_version: str
    occurred_at: str
    station_id: str
    principal_id: str
    session_id: str
    source: str
    subject: str
    payload: Mapping[str, Any]
    correlation_id: str
    causation_id: str | None
    classification: str
