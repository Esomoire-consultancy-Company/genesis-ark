from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json

from cloudbrowser_service.evidence import build_event
from cloudbrowser_service.models import (
    ActionDecision,
    BrowserAction,
    BrowserActionRequest,
    BrowserActionType,
)
from cloudbrowser_service.postgres_repository import PostgresCloudBrowserRepository


class FakeCursor:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 1
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        self.executed.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.responses.pop(0) if self.responses else None

    def fetchall(self):
        value = self.responses.pop(0) if self.responses else []
        return value or []


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_object = cursor
        self.transactions = 0

    def cursor(self):
        return self.cursor_object

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield


class FakePool:
    def __init__(self, responses=None):
        self.cursor = FakeCursor(responses)
        self.connection_object = FakeConnection(self.cursor)
        self.connections = 0

    @contextmanager
    def connection(self, timeout=None):
        self.connections += 1
        yield self.connection_object


def test_action_persistence_keeps_original_sanitized_request() -> None:
    now = datetime.now(timezone.utc)
    request = BrowserActionRequest(
        action_id="BROWSER-ACTION-PERSIST-001",
        action_type=BrowserActionType.SUBMIT_FORM,
        target_url="https://example.com/orders",
        purpose="TEST",
        data_classes=["FORM_DATA"],
        payload={"fields": {"#quantity": "2"}, "submit_selector": "#submit"},
    )
    action = BrowserAction(
        action_id=request.action_id,
        browser_session_id="BROWSER-SESSION-PERSIST-001",
        action_type=request.action_type,
        decision=ActionDecision.APPROVAL_REQUIRED,
        reason_codes=["HUMAN_APPROVAL_REQUIRED"],
        target_url=str(request.target_url),
        warden_policy_decision_id="DECISION-PERSIST-001",
        capability_id="CAPABILITY-PERSIST-001",
        approval_id="APPROVAL-PERSIST-001",
        requested_at=now,
        decided_at=now,
        evidence_event_id="BROWSER-EVENT-PERSIST-001",
    ).bind_request(request)
    pool = FakePool()
    repository = PostgresCloudBrowserRepository("", pool=pool)

    event = build_event(
        browser_session_id=action.browser_session_id,
        box_id="BOX-PERSIST-001",
        event_type="HUMAN_APPROVAL_REQUESTED",
        actor_id="DIGITALME-PERSIST-001",
        action_reference=action.action_id,
        payload={"approval_id": action.approval_id},
        previous_event_hash=None,
        timestamp=now,
    )
    repository.record_action(action, event)

    statement, params = next(
        item for item in pool.cursor.executed if "insert into cloud_browser_actions" in item[0]
    )
    assert "insert into cloud_browser_actions" in statement
    request_payload = json.loads(params[9])
    assert request_payload["payload"]["fields"]["#quantity"] == "2"
    assert request_payload["payload"]["submit_selector"] == "#submit"


def test_browser_evidence_append_is_serialized_in_one_transaction() -> None:
    now = datetime.now(timezone.utc)
    event = build_event(
        browser_session_id="BROWSER-SESSION-EVIDENCE-001",
        box_id="BOX-EVIDENCE-001",
        event_type="BROWSER_ACTION_EXECUTED",
        actor_id="DIGITALME-EVIDENCE-001",
        action_reference="ACTION-EVIDENCE-001",
        payload={"ok": True},
        previous_event_hash=None,
        timestamp=now,
    )
    pool = FakePool([None])
    repository = PostgresCloudBrowserRepository("", pool=pool)

    repository.append_evidence(event)

    sql = "\n".join(statement for statement, _ in pool.cursor.executed)
    assert pool.connections == 1
    assert "pg_advisory_xact_lock" in sql
    assert "insert into cloud_browser_evidence_events" in sql
