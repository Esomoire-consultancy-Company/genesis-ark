from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from warden_service.app import create_app
from warden_service.config import Settings
from warden_service.models import (
    ActorBoxRecord,
    BindingRecord,
    BoundaryRuleRecord,
    BoxStatus,
    ConsentRecord,
    ContextRecord,
    ControlStatus,
    DelegationRecord,
    PolicyProfileRecord,
    RuntimeIntegrity,
    RuntimeRecord,
)
from warden_service.repository import InMemoryRegistry

BOX_ID = "BOX-GENESIS-PERSONAL-0001"
RUNTIME_ID = "RUNTIME-GENESIS-PHONE-0001"
SUBJECT_ID = "DIGITALME-FAIZ-0001"
AGENT_ID = "AGENT-INVENTORY-RECONCILIATION-0001"
CONTEXT_ID = "CONTEXT-VOI-CIRP-OPERATIONS-0001"
WORKSPACE_ID = "VOI-CIRP-OPERATIONS"
PURPOSE = "DAILY_STOCK_RECONCILIATION"
ACTION = "READ_AND_RECONCILE"
AUTH_HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Client-Cert-Verified": "SUCCESS",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def seeded_registry() -> InMemoryRegistry:
    at = now()
    registry = InMemoryRegistry()
    registry.boxes[BOX_ID] = ActorBoxRecord(
        box_id=BOX_ID,
        status=BoxStatus.ACTIVE,
        policy_profile_id="WARDEN-POLICY-PERSONAL-V1",
        evidence_stream_id="RIVER-BOX-0001",
        updated_at=at,
    )
    registry.runtimes[RUNTIME_ID] = RuntimeRecord(
        runtime_id=RUNTIME_ID,
        box_id=BOX_ID,
        integrity_status=RuntimeIntegrity.ATTESTED,
        last_attested_at=at,
    )
    registry.bindings["BINDING-FAIZ-0001"] = BindingRecord(
        binding_id="BINDING-FAIZ-0001",
        box_id=BOX_ID,
        digitalme_id=SUBJECT_ID,
        status=ControlStatus.ACTIVE,
        effective_from=at - timedelta(days=1),
    )
    registry.contexts[CONTEXT_ID] = ContextRecord(
        context_id=CONTEXT_ID,
        box_id=BOX_ID,
        principal_id=SUBJECT_ID,
        workspace_id=WORKSPACE_ID,
        status=ControlStatus.ACTIVE,
        activated_at=at - timedelta(hours=1),
        expires_at=at + timedelta(hours=8),
    )
    registry.policy_profiles["WARDEN-POLICY-PERSONAL-V1"] = PolicyProfileRecord(
        policy_profile_id="WARDEN-POLICY-PERSONAL-V1",
        box_id=BOX_ID,
        policy_bundle_version="warden-actor-box-v1.0.0",
        status=ControlStatus.ACTIVE,
        effective_from=at - timedelta(days=1),
        max_capability_ttl_seconds=1200,
    )
    registry.consents["CONSENT-INVENTORY-0001"] = ConsentRecord(
        consent_receipt_id="CONSENT-INVENTORY-0001",
        box_id=BOX_ID,
        digitalme_id=SUBJECT_ID,
        purpose=PURPOSE,
        data_scope=["INVENTORY", "OPERATIONAL"],
        action_scope=[ACTION, "READ_ONLY"],
        status=ControlStatus.ACTIVE,
        effective_from=at - timedelta(days=1),
    )
    registry.delegations["DELEGATION-INVENTORY-0001"] = DelegationRecord(
        delegation_id="DELEGATION-INVENTORY-0001",
        box_id=BOX_ID,
        agent_id=AGENT_ID,
        delegating_principal_id=SUBJECT_ID,
        permitted_actions=[ACTION, "READ_ONLY"],
        permitted_data_scope=["INVENTORY", "OPERATIONAL"],
        workspace_scope=[WORKSPACE_ID],
        status=ControlStatus.ACTIVE,
        effective_from=at - timedelta(days=1),
        write_requires_human_approval=True,
    )
    for index, data_class in enumerate(("INVENTORY", "OPERATIONAL"), start=1):
        registry.boundaries[f"BOUNDARY-{index:04d}"] = BoundaryRuleRecord(
            boundary_rule_id=f"BOUNDARY-{index:04d}",
            box_id=BOX_ID,
            source_zone="ORGANISATION",
            destination_zone="SHARED_WORKSPACE",
            data_class=data_class,
            permitted_purpose=PURPOSE,
            status=ControlStatus.ACTIVE,
            effective_from=at - timedelta(days=1),
        )
    return registry


@pytest.fixture
def registry() -> InMemoryRegistry:
    return seeded_registry()


@pytest.fixture
def client(registry: InMemoryRegistry) -> TestClient:
    app = create_app(
        registry=registry,
        settings=Settings(api_token="test-token"),
    )
    return TestClient(app)


def decision_request(*, agent: bool = True, approval: bool = False) -> dict:
    payload = {
        "request_id": f"REQ-{now().timestamp():.6f}".replace(".", "-"),
        "requested_at": now().isoformat(),
        "box_id": BOX_ID,
        "runtime_id": RUNTIME_ID,
        "subject_id": SUBJECT_ID,
        "context_id": CONTEXT_ID,
        "resource_id": "DODDABALLAPUR-INVENTORY-VIEW",
        "requested_action": ACTION,
        "purpose": PURPOSE,
        "data_classes": ["INVENTORY", "OPERATIONAL"],
        "source_zone": "ORGANISATION",
        "destination_zone": "SHARED_WORKSPACE",
        "requested_duration_seconds": 1200,
        "human_approval_present": approval,
    }
    if agent:
        payload["agent_id"] = AGENT_ID
    return payload
