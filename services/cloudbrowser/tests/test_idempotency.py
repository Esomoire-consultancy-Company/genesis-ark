from __future__ import annotations

from cloudbrowser_service.app import create_app
from cloudbrowser_service.config import Settings
from cloudbrowser_service.executor import DeterministicBrowserExecutor
from fastapi.testclient import TestClient

from conftest import AUTH_HEADERS, SUBJECT_ID, create_session


class RecordingExecutor(DeterministicBrowserExecutor):
    def __init__(self) -> None:
        self.executions = 0

    def execute(self, session, action, policy):
        self.executions += 1
        return super().execute(session, action, policy)


def test_repeated_action_id_returns_recorded_result_without_reexecution(
    repository,
    warden_registry_and_client,
) -> None:
    _, warden = warden_registry_and_client
    executor = RecordingExecutor()
    app = create_app(
        repository=repository,
        warden=warden,
        executor=executor,
        settings=Settings(api_token="cloudbrowser-test-token"),
    )
    with TestClient(app) as client:
        session_id = create_session(client)["browser_session_id"]
        payload = {
            "action_id": "BROWSER-ACTION-IDEMPOTENT-001",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://example.com/dashboard",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
        }
        first = client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json=payload,
        )
        second = client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json=payload,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == first.json()
        assert executor.executions == 1
        assert len(repository.list_evidence(session_id)) == 3


def test_action_id_cannot_be_reused_for_different_request(
    repository,
    warden_registry_and_client,
) -> None:
    _, warden = warden_registry_and_client
    app = create_app(
        repository=repository,
        warden=warden,
        executor=RecordingExecutor(),
        settings=Settings(api_token="cloudbrowser-test-token"),
    )
    with TestClient(app) as client:
        session_id = create_session(client)["browser_session_id"]
        original = {
            "action_id": "BROWSER-ACTION-IDEMPOTENT-002",
            "action_type": "BROWSER_NAVIGATE",
            "target_url": "https://example.com/one",
            "purpose": "CLOUD_BROWSER_OPERATION",
            "data_classes": ["PUBLIC"],
        }
        assert client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json=original,
        ).status_code == 200

        changed = {**original, "target_url": "https://example.com/two"}
        response = client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json=changed,
        )
        assert response.status_code == 409
        assert "different request" in response.json()["detail"]


def test_approved_action_cannot_be_approved_twice(
    repository,
    warden_registry_and_client,
) -> None:
    _, warden = warden_registry_and_client
    app = create_app(
        repository=repository,
        warden=warden,
        executor=RecordingExecutor(),
        settings=Settings(api_token="cloudbrowser-test-token"),
    )
    with TestClient(app) as client:
        session_id = create_session(client)["browser_session_id"]
        pending = client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json={
                "action_id": "BROWSER-ACTION-APPROVAL-ONCE-001",
                "action_type": "BROWSER_SUBMIT_FORM",
                "target_url": "https://example.com/orders",
                "purpose": "CLOUD_BROWSER_OPERATION",
                "data_classes": ["FORM_DATA"],
                "payload": {
                    "fields": {"#quantity": "1"},
                    "submit_selector": "#submit",
                },
            },
        )
        assert pending.status_code == 200
        approval = {
            "action_id": "BROWSER-ACTION-APPROVAL-ONCE-001",
            "approved_by": SUBJECT_ID,
            "approval_reason": "Verified exact action",
        }
        assert client.post(
            f"/v1/browser-sessions/{session_id}/approve",
            headers=AUTH_HEADERS,
            json=approval,
        ).status_code == 200
        replay = client.post(
            f"/v1/browser-sessions/{session_id}/approve",
            headers=AUTH_HEADERS,
            json=approval,
        )
        assert replay.status_code == 409
