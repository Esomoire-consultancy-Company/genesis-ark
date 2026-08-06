from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cloudbrowser_service.app import create_app
from cloudbrowser_service.config import Settings
from cloudbrowser_service.models import BrowserActionType, BrowserPolicy
from cloudbrowser_service.repository import InMemoryCloudBrowserRepository
from warden_service.config import Settings as WardenSettings
from warden_service.engine import WardenEngine
from warden_service.evidence import utcnow
from warden_service.models import (
    ActorBoxRecord,
    BindingRecord,
    BoundaryRuleRecord,
    BoxStatus,
    ConsentRecord,
    ContextRecord,
    ControlStatus,
    PolicyDecisionRequest,
    PolicyProfileRecord,
    RevocationRequest,
    RuntimeIntegrity,
    RuntimeRecord,
    CapabilityIssueRequest,
)
from warden_service.repository import InMemoryRegistry

BOX_ID = "BOX-CLOUDBROWSER-0001"
SUBJECT_ID = "DIGITALME-FAIZ-0001"
RUNTIME_ID = "RUNTIME-GENESIS-PHONE-0001"
CONTEXT_ID = "CONTEXT-VSR-OPERATIONS-0001"
WORKSPACE_ID = "WORKSPACE-VSR-OPERATIONS-0001"
POLICY_ID = "BROWSER-POLICY-GOVERNED-V1"
PURPOSE = "CLOUD_BROWSER_OPERATION"
AUTH_HEADERS = {
    "Authorization": "Bearer cloudbrowser-test-token",
    "X-Client-Cert-Verified": "SUCCESS",
}


class InProcessWardenClient:
    def __init__(self, engine: WardenEngine) -> None:
        self.engine = engine

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        decision = self.engine.evaluate(PolicyDecisionRequest.model_validate(payload))
        return decision.model_dump(mode="json")

    def issue(self, policy_decision_id: str, requested_by: str) -> dict[str, Any]:
        capability = self.engine.issue_capability(
            CapabilityIssueRequest(
                policy_decision_id=policy_decision_id,
                requested_by=requested_by,
            )
        )
        return capability.model_dump(mode="json")

    def revoke(
        self,
        capability_id: str,
        *,
        reason: str,
        revoked_by: str,
        policy_reference: str,
    ) -> dict[str, Any]:
        revocation = self.engine.revoke_capability(
            capability_id,
            RevocationRequest(
                reason=reason,
                revoked_by=revoked_by,
                policy_reference=policy_reference,
            ),
        )
        return revocation.model_dump(mode="json")


def seed_warden() -> tuple[InMemoryRegistry, WardenEngine]:
    now = utcnow()
    registry = InMemoryRegistry()
    registry.boxes[BOX_ID] = ActorBoxRecord(
        box_id=BOX_ID,
        status=BoxStatus.ACTIVE,
        policy_profile_id="WARDEN-POLICY-CLOUDBROWSER-V1",
        evidence_stream_id="RIVER-CLOUDBROWSER-BOX-0001",
        updated_at=now,
    )
    registry.runtimes[RUNTIME_ID] = RuntimeRecord(
        runtime_id=RUNTIME_ID,
        box_id=BOX_ID,
        integrity_status=RuntimeIntegrity.ATTESTED,
        last_attested_at=now,
    )
    registry.bindings["BINDING-CLOUDBROWSER-0001"] = BindingRecord(
        binding_id="BINDING-CLOUDBROWSER-0001",
        box_id=BOX_ID,
        digitalme_id=SUBJECT_ID,
        status=ControlStatus.ACTIVE,
        effective_from=now - timedelta(minutes=5),
    )
    registry.contexts[CONTEXT_ID] = ContextRecord(
        context_id=CONTEXT_ID,
        box_id=BOX_ID,
        principal_id=SUBJECT_ID,
        workspace_id=WORKSPACE_ID,
        status=ControlStatus.ACTIVE,
        activated_at=now - timedelta(minutes=5),
    )
    registry.policy_profiles["WARDEN-POLICY-CLOUDBROWSER-V1"] = PolicyProfileRecord(
        policy_profile_id="WARDEN-POLICY-CLOUDBROWSER-V1",
        box_id=BOX_ID,
        policy_bundle_version="warden-cloudbrowser-v1.0.0",
        status=ControlStatus.ACTIVE,
        effective_from=now - timedelta(minutes=5),
        max_capability_ttl_seconds=1800,
    )
    registry.consents["CONSENT-CLOUDBROWSER-0001"] = ConsentRecord(
        consent_receipt_id="CONSENT-CLOUDBROWSER-0001",
        box_id=BOX_ID,
        digitalme_id=SUBJECT_ID,
        purpose=PURPOSE,
        data_scope=["PUBLIC", "FORM_DATA", "CREDENTIAL_REFERENCE"],
        action_scope=[
            "BROWSER_SESSION_START",
            "BROWSER_NAVIGATE",
            "BROWSER_READ_PAGE",
            "BROWSER_SUBMIT_FORM",
            "BROWSER_USE_CREDENTIAL",
            "BROWSER_UPLOAD_FILE",
        ],
        status=ControlStatus.ACTIVE,
        effective_from=now - timedelta(minutes=5),
    )
    for data_class in ["FORM_DATA", "CREDENTIAL_REFERENCE"]:
        rule_id = f"BOUNDARY-{data_class}"
        registry.boundaries[rule_id] = BoundaryRuleRecord(
            boundary_rule_id=rule_id,
            box_id=BOX_ID,
            source_zone="ORGANISATION",
            destination_zone="EXTERNAL_PROVIDER",
            data_class=data_class,
            permitted_purpose=PURPOSE,
            status=ControlStatus.ACTIVE,
            effective_from=now - timedelta(minutes=5),
        )
    engine = WardenEngine(
        registry,
        WardenSettings(
            api_token="warden-test-token",
            max_capability_ttl_seconds=1800,
        ),
    )
    return registry, engine


@pytest.fixture
def repository() -> InMemoryCloudBrowserRepository:
    repository = InMemoryCloudBrowserRepository()
    repository.policies[POLICY_ID] = BrowserPolicy(
        policy_id=POLICY_ID,
        allowed_domains=["example.com", "*.trusted.example"],
        allowed_actions=[
            BrowserActionType.NAVIGATE,
            BrowserActionType.READ_PAGE,
            BrowserActionType.SUBMIT_FORM,
            BrowserActionType.USE_CREDENTIAL,
            BrowserActionType.UPLOAD_FILE,
        ],
        high_impact_actions=[BrowserActionType.SUBMIT_FORM],
        allow_credentials=True,
        allow_uploads=False,
        allow_downloads=False,
        allow_clipboard=False,
        allow_screen_capture=False,
        max_file_bytes=1_000_000,
    )
    return repository


@pytest.fixture
def warden_registry_and_client():
    registry, engine = seed_warden()
    return registry, InProcessWardenClient(engine)


@pytest.fixture
def client(repository, warden_registry_and_client) -> TestClient:
    _, warden = warden_registry_and_client
    app = create_app(
        repository=repository,
        warden=warden,
        settings=Settings(
            api_token="cloudbrowser-test-token",
            approval_ttl_seconds=300,
        ),
    )
    return TestClient(app)


def session_request() -> dict[str, Any]:
    return {
        "request_id": "BROWSER-SESSION-REQUEST-0001",
        "box_id": BOX_ID,
        "digitalme_id": SUBJECT_ID,
        "runtime_id": RUNTIME_ID,
        "context_id": CONTEXT_ID,
        "workspace_id": WORKSPACE_ID,
        "policy_id": POLICY_ID,
        "purpose": PURPOSE,
        "data_classes": ["PUBLIC"],
        "requested_duration_seconds": 1200,
    }


def create_session(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/v1/browser-sessions",
        headers=AUTH_HEADERS,
        json=session_request(),
    )
    assert response.status_code == 201, response.text
    return response.json()
