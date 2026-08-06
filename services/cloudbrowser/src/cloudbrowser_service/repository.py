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
    UsageRecord,
)


class CloudBrowserRepository(Protocol):
    def get_policy(self, policy_id: str) -> BrowserPolicy | None: ...
    def create_session(
        self,
        session: BrowserSession,
        usage: UsageRecord,
        event: EvidenceEvent,
    ) -> BrowserSession: ...
    def get_session(self, session_id: str) -> BrowserSession | None: ...
    def transition_session(
        self,
        session: BrowserSession,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserSession: ...
    def record_action(
        self,
        action: BrowserAction,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserAction: ...
    def record_approval_grant(
        self,
        approval: BrowserApproval,
        action: BrowserAction,
        approval_event: EvidenceEvent,
        usage: UsageRecord,
    ) -> BrowserAction: ...
    def get_action(self, action_id: str) -> BrowserAction | None: ...
    def get_approval(self, approval_id: str) -> BrowserApproval | None: ...
    def get_usage(self, session_id: str) -> UsageRecord | None: ...
    def save_usage(self, usage: UsageRecord) -> UsageRecord: ...
    def append_evidence(self, event: EvidenceEvent) -> None: ...
    def latest_evidence(self, session_id: str) -> EvidenceEvent | None: ...
    def list_evidence(self, session_id: str) -> list[EvidenceEvent]: ...
    def list_session_actions(self, session_id: str) -> list[BrowserAction]: ...
    def open(self) -> None: ...
    def close(self) -> None: ...


class InMemoryCloudBrowserRepository:
    def __init__(self) -> None:
        self.policies: dict[str, BrowserPolicy] = {}
        self.sessions: dict[str, BrowserSession] = {}
        self.actions: dict[str, BrowserAction] = {}
        self.approvals: dict[str, BrowserApproval] = {}
        self.usage: dict[str, UsageRecord] = {}
        self.evidence: list[EvidenceEvent] = []
        self._lock = RLock()

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def get_policy(self, policy_id: str) -> BrowserPolicy | None:
        return self.policies.get(policy_id)

    def _append_evidence_locked(self, event: EvidenceEvent) -> None:
        latest = self.latest_evidence(event.browser_session_id)
        expected = latest.evidence_hash if latest else None
        if event.previous_event_hash != expected:
            raise StateConflictError("Evidence event does not continue the session hash chain")
        self.evidence.append(event)

    def create_session(
        self,
        session: BrowserSession,
        usage: UsageRecord,
        event: EvidenceEvent,
    ) -> BrowserSession:
        with self._lock:
            if session.browser_session_id in self.sessions:
                raise StateConflictError("Browser session ID already exists")
            if usage.browser_session_id != session.browser_session_id:
                raise StateConflictError("Usage meter is bound to another session")
            self.sessions[session.browser_session_id] = session
            self.usage[session.browser_session_id] = usage
            self._append_evidence_locked(event)
            return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self.sessions.get(session_id)

    def transition_session(
        self,
        session: BrowserSession,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserSession:
        with self._lock:
            if session.browser_session_id not in self.sessions:
                raise NotFoundError(f"Browser session {session.browser_session_id} does not exist")
            self._append_evidence_locked(event)
            self.sessions[session.browser_session_id] = session
            if usage is not None:
                self.usage[session.browser_session_id] = usage
            return session

    def record_action(
        self,
        action: BrowserAction,
        event: EvidenceEvent,
        usage: UsageRecord | None = None,
    ) -> BrowserAction:
        with self._lock:
            existing = self.actions.get(action.action_id)
            if existing is not None and existing.browser_session_id != action.browser_session_id:
                raise StateConflictError("Action ID is already bound to another session")
            self._append_evidence_locked(event)
            self.actions[action.action_id] = action
            if usage is not None:
                self.usage[action.browser_session_id] = usage
            return action

    def record_approval_grant(
        self,
        approval: BrowserApproval,
        action: BrowserAction,
        approval_event: EvidenceEvent,
        usage: UsageRecord,
    ) -> BrowserAction:
        with self._lock:
            if approval.approval_id in self.approvals:
                raise StateConflictError("Approval ID already exists")
            existing = self.actions.get(action.action_id)
            if existing is None:
                raise NotFoundError(f"Browser action {action.action_id} does not exist")
            if str(existing.decision) != "APPROVAL_REQUIRED":
                raise StateConflictError("Browser action is not awaiting approval")
            self._append_evidence_locked(approval_event)
            self.approvals[approval.approval_id] = approval
            self.actions[action.action_id] = action
            self.usage[action.browser_session_id] = usage
            return action

    def get_action(self, action_id: str) -> BrowserAction | None:
        return self.actions.get(action_id)

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
            self._append_evidence_locked(event)

    def latest_evidence(self, session_id: str) -> EvidenceEvent | None:
        return next(
            (event for event in reversed(self.evidence) if event.browser_session_id == session_id),
            None,
        )

    def list_evidence(self, session_id: str) -> list[EvidenceEvent]:
        return [event for event in self.evidence if event.browser_session_id == session_id]

    def list_session_actions(self, session_id: str) -> list[BrowserAction]:
        return [action for action in self.actions.values() if action.browser_session_id == session_id]
