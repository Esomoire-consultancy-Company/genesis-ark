from __future__ import annotations

from cloudbrowser_service.app import create_app
from cloudbrowser_service.config import Settings
from cloudbrowser_service.executor import DeterministicBrowserExecutor
from fastapi.testclient import TestClient

from conftest import AUTH_HEADERS, SUBJECT_ID, create_session


class RecordingExecutor(DeterministicBrowserExecutor):
    def __init__(self) -> None:
        self.executed = []

    def execute(self, session, action, policy):
        self.executed.append(action)
        return super().execute(session, action, policy)


def test_approval_replays_original_sanitized_action(
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
        original_payload = {
            "fields": {"#quantity": "2", "#sku": "SKU-001"},
            "submit_selector": "#submit",
        }
        pending = client.post(
            f"/v1/browser-sessions/{session_id}/actions/evaluate",
            headers=AUTH_HEADERS,
            json={
                "action_id": "BROWSER-ACTION-REPLAY-001",
                "action_type": "BROWSER_SUBMIT_FORM",
                "target_url": "https://example.com/orders",
                "purpose": "CLOUD_BROWSER_OPERATION",
                "data_classes": ["FORM_DATA"],
                "payload": original_payload,
            },
        )
        assert pending.status_code == 200
        assert pending.json()["decision"] == "APPROVAL_REQUIRED"

        approved = client.post(
            f"/v1/browser-sessions/{session_id}/approve",
            headers=AUTH_HEADERS,
            json={
                "action_id": "BROWSER-ACTION-REPLAY-001",
                "approved_by": SUBJECT_ID,
                "approval_reason": "Verified exact order contents",
            },
        )
        assert approved.status_code == 200, approved.text
        assert executor.executed[-1].payload == original_payload
        assert executor.executed[-1].purpose == "CLOUD_BROWSER_OPERATION"
