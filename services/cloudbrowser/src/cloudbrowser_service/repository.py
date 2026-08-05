from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Protocol

from .errors import NotFoundError, StateConflictError
from .models import (
    BrowserAction,
    BrowserApproval,
    BrowserPolicy,
    BrowserSession,
    EvidenceEvent,
    SessionStatus,
    UsageRecord,
)


class CloudBrowserRepository(Protocol):
    def get_policy(self, policy_id: str) -> BrowserPolicy | None: ...
    def save_session(self, session: BrowserSession) -> BrowserSession: ...
    def get_session(self, session_id: str) -> BrowserSession | None: ...
    def update_session(self, session: BrowserSession) -> BrowserSession: ...
    def save_action(self, action: BrowserAction) -> BrowserAction: ...
    def get_action(self, action_id: str) -> BrowserAction | None: ...
    def save_approval(self, approval: BrowserApproval) -> BrowserApproval: ...
    def get_approval(self, approval_id: str) -> BrowserApproval | None: ...
    def get_usage(self, session_id: str) -> UsageRecord | None: ...
    def save_usage(self, usage: UsageRecord) -> UsageRecord: ...
    def append_evidence(self, event: EvidenceEvent) -> None: ...
    def latest_evidence(self, session_id: str) -> EvidenceEvent | None: ...
    def list_evidence(self, session_id: str) -> list[EvidenceEvent]: ...
    def list_session_actions(self, session_id: str) -> list[BrowserAction]: ...


class InMemoryCloudBrowserRepository:
    def __init__(self) -> None:
        self.policies: dict[str, BrowserPolicy] = {}
        self.sessions: dict[str, BrowserSession] = {}
        self.actions: dict[str, BrowserAction] = {}
        self.approvals: dict[str, BrowserApproval] = {}
        self.usage: dict[str, UsageRecord] = {}
        self.evidence: list[EvidenceEvent] = []
        self._lock = RLock()

    def get_policy(self, policy_id: str) -> BrowserPolicy | None:
        return self.policies.get(policy_id)

    def save_session(self, session: BrowserSession) -> BrowserSession:
        with self._lock:
            if session.browser_session_id in self.sessions:
                raise StateConflictError("Browser session ID already exists")
            self.sessions[session.browser_session_id] = session
            return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self.sessions.get(session_id)

    def update_session(self, session: BrowserSession) -> BrowserSession:
        with self._lock:
            if session.browser_session_id not in self.sessions:
                raise NotFoundError(f"Browser session {session.browser_session_id} does not exist")
            self.sessions[session.browser_session_id] = session
            return session

    def save_action(self, action: BrowserAction) -> BrowserAction:
        with self._lock:
            existing = self.actions.get(action.action_id)
            if existing is not None and existing.browser_session_id != action.browser_session_id:
                raise StateConflictError("Action ID is already bound to another session")
            self.actions[action.action_id] = action
            return action

    def get_action(self, action_id: str) -> BrowserAction | None:
        return self.actions.get(action_id)

    def save_approval(self, approval: BrowserApproval) -> BrowserApproval:
        with self._lock:
            if approval.approval_id in self.approvals:
                raise StateConflictError("Approval ID already exists")
            self.approvals[approval.approval_id] = approval
            return approval

    def get_approval(self, approval_id: str) -> BrowserApproval | None:
        return self.approvals.get(approval_id)

    def get_usage(self, session_id: str) -> UsageRecord | None:
        return self.usage.get(session_id)

    def save_usage(self, usage: UsageRecord) -> UsageRecord:
        with self._lock:
            self.usage[usage.browser_session_id] = usage
            return usage

    def append_evidence(self, event: EvidenceEvent) -> None:
        with self._lock:
            latest = self.latest_evidence(event.browser_session_id)
            expected = latest.evidence_hash if latest else None
            if event.previous_event_hash != expected:
                raise StateConflictError("Evidence event does not continue the session hash chain")
            self.evidence.append(event)

    def latest_evidence(self, session_id: str) -> EvidenceEvent | None:
        return next(
            (event for event in reversed(self.evidence) if event.browser_session_id == session_id),
            None,
        )

    def list_evidence(self, session_id: str) -> list[EvidenceEvent]:
        return [event for event in self.evidence if event.browser_session_id == session_id]

    def list_session_actions(self, session_id: str) -> list[BrowserAction]:
        return [action for action in self.actions.values() if action.browser_session_id == session_id]
