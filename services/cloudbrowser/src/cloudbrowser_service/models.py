from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Identifier = Annotated[
    str,
    Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"
    EXPIRED = "EXPIRED"
    LOCKED = "LOCKED"


class BrowserActionType(StrEnum):
    NAVIGATE = "BROWSER_NAVIGATE"
    READ_PAGE = "BROWSER_READ_PAGE"
    FILL_FORM = "BROWSER_FILL_FORM"
    SUBMIT_FORM = "BROWSER_SUBMIT_FORM"
    UPLOAD_FILE = "BROWSER_UPLOAD_FILE"
    DOWNLOAD_FILE = "BROWSER_DOWNLOAD_FILE"
    USE_CLIPBOARD = "BROWSER_USE_CLIPBOARD"
    OPEN_CONNECTOR = "BROWSER_OPEN_CONNECTOR"
    USE_CREDENTIAL = "BROWSER_USE_CREDENTIAL"
    RUN_AGENT = "BROWSER_RUN_AGENT"
    CAPTURE_SCREEN = "BROWSER_CAPTURE_SCREEN"
    EXPORT_RESULT = "BROWSER_EXPORT_RESULT"
    SEND_MESSAGE = "BROWSER_SEND_MESSAGE"
    PLACE_ORDER = "BROWSER_PLACE_ORDER"
    ACCEPT_TERMS = "BROWSER_ACCEPT_TERMS"
    CHANGE_ACCOUNT = "BROWSER_CHANGE_ACCOUNT"
    PUBLISH_CONTENT = "BROWSER_PUBLISH_CONTENT"
    INITIATE_PAYMENT = "BROWSER_INITIATE_PAYMENT"
    DELETE_RECORD = "BROWSER_DELETE_RECORD"
    TRANSFER_ASSET = "BROWSER_TRANSFER_ASSET"


class ActionDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"


class BrowserPolicy(StrictModel):
    policy_id: Identifier
    allowed_domains: list[str] = Field(min_length=1)
    allowed_actions: list[BrowserActionType] = Field(min_length=1)
    high_impact_actions: list[BrowserActionType]
    allow_uploads: bool = False
    allow_downloads: bool = False
    allow_clipboard: bool = False
    allow_credentials: bool = False
    allow_screen_capture: bool = False
    allow_sensors: bool = False
    max_file_bytes: int = Field(default=10_000_000, ge=0)


class BrowserSessionRequest(StrictModel):
    request_id: Identifier
    box_id: Identifier
    digitalme_id: Identifier
    runtime_id: Identifier
    context_id: Identifier
    workspace_id: Identifier
    licence_id: Identifier | None = None
    agent_id: Identifier | None = None
    policy_id: Identifier
    purpose: str = Field(min_length=1)
    data_classes: list[str]
    requested_duration_seconds: int = Field(ge=1, le=3600)


class BrowserSession(StrictModel):
    browser_session_id: Identifier
    box_id: Identifier
    digitalme_id: Identifier
    runtime_id: Identifier
    context_id: Identifier
    workspace_id: Identifier
    licence_id: Identifier | None = None
    agent_id: Identifier | None = None
    policy_id: Identifier
    policy_decision_id: Identifier
    capability_id: Identifier
    session_status: SessionStatus
    isolation_profile: str
    started_at: datetime
    expires_at: datetime
    terminated_at: datetime | None = None
    evidence_stream_id: Identifier
    compute_meter_id: Identifier


class BrowserActionRequest(StrictModel):
    action_id: Identifier
    action_type: BrowserActionType
    target_url: HttpUrl | None = None
    purpose: str = Field(min_length=1)
    data_classes: list[str]
    payload: dict[str, Any] = Field(default_factory=dict)
    estimated_network_bytes: int = Field(default=0, ge=0)
    estimated_file_bytes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def target_required_for_navigation(self) -> "BrowserActionRequest":
        if self.action_type in {
            BrowserActionType.NAVIGATE,
            BrowserActionType.READ_PAGE,
            BrowserActionType.FILL_FORM,
            BrowserActionType.SUBMIT_FORM,
            BrowserActionType.DOWNLOAD_FILE,
            BrowserActionType.UPLOAD_FILE,
        } and self.target_url is None:
            raise ValueError("target_url is required for this browser action")
        return self


class BrowserAction(StrictModel):
    action_id: Identifier
    browser_session_id: Identifier
    action_type: BrowserActionType
    decision: ActionDecision
    reason_codes: list[str] = Field(min_length=1)
    target_url: str | None = None
    warden_policy_decision_id: Identifier | None = None
    capability_id: Identifier | None = None
    approval_id: Identifier | None = None
    requested_at: datetime
    decided_at: datetime
    executed_at: datetime | None = None
    result: dict[str, Any] | None = None
    evidence_event_id: Identifier


class BrowserApprovalRequest(StrictModel):
    action_id: Identifier
    approved_by: Identifier
    approval_reason: str = Field(min_length=1)


class BrowserApproval(StrictModel):
    approval_id: Identifier
    browser_session_id: Identifier
    action_id: Identifier
    approved_by: Identifier
    approved_at: datetime
    expires_at: datetime
    evidence_event_id: Identifier


class SessionPauseRequest(StrictModel):
    paused_by: Identifier
    reason: str = Field(min_length=1)


class SessionTerminateRequest(StrictModel):
    terminated_by: Identifier
    reason: str = Field(min_length=1)


class UsageRecord(StrictModel):
    compute_meter_id: Identifier
    browser_session_id: Identifier
    runtime_seconds: int = Field(ge=0)
    action_count: int = Field(ge=0)
    approval_count: int = Field(ge=0)
    connector_calls: int = Field(ge=0)
    uploaded_bytes: int = Field(ge=0)
    downloaded_bytes: int = Field(ge=0)
    network_bytes: int = Field(ge=0)
    compute_units: float = Field(ge=0)
    updated_at: datetime


class EvidenceEvent(StrictModel):
    event_id: Identifier
    browser_session_id: Identifier
    box_id: Identifier
    event_type: str
    actor_id: Identifier
    action_reference: str
    timestamp: datetime
    payload: dict[str, Any]
    previous_event_hash: str | None = None
    evidence_hash: str
