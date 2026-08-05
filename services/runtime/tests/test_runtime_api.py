from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import (
    AUTH_HEADERS,
    INSTANCE_ID,
    RESOURCE_CAPABILITY_ID,
    SESSION_ID,
    instance_request,
    node_request,
    seed_active_instance,
    session_request,
)


def test_authentication_requires_mtls_and_bearer(client: TestClient) -> None:
    response = client.post("/v1/runtime-nodes", json=node_request())
    assert response.status_code == 401
    assert "MTLS_NOT_VERIFIED" in response.json()["reason_codes"]


def test_register_provision_and_attest_instance(client: TestClient) -> None:
    node = client.post(
        "/v1/runtime-nodes", headers=AUTH_HEADERS, json=node_request()
    )
    assert node.status_code == 201, node.text
    assert node.json()["status"] == "ACTIVE"

    provisioned = client.post(
        "/v1/runtime-instances", headers=AUTH_HEADERS, json=instance_request()
    )
    assert provisioned.status_code == 201, provisioned.text
    assert provisioned.json()["status"] == "PROVISIONING"

    attested = client.post(
        f"/v1/runtime-instances/{INSTANCE_ID}/attest",
        headers=AUTH_HEADERS,
        json={
            "integrity_status": "ATTESTED",
            "attestation_reference": "ATTEST-INSTANCE-001",
            "attested_by": "GENESIS-ATTESTOR-001",
        },
    )
    assert attested.status_code == 200, attested.text
    assert attested.json()["status"] == "ACTIVE"
    assert attested.json()["integrity_status"] == "ATTESTED"


def test_unattested_instance_cannot_start_session(client: TestClient) -> None:
    client.post("/v1/runtime-nodes", headers=AUTH_HEADERS, json=node_request())
    client.post(
        "/v1/runtime-instances", headers=AUTH_HEADERS, json=instance_request()
    )

    response = client.post(
        "/v1/runtime-sessions", headers=AUTH_HEADERS, json=session_request()
    )
    assert response.status_code == 409
    assert "INSTANCE_PROVISIONING" in response.json()["reason_codes"]


def test_capability_aware_session_and_resource_allocation(
    client: TestClient,
) -> None:
    seed_active_instance(client)
    started = client.post(
        "/v1/runtime-sessions", headers=AUTH_HEADERS, json=session_request()
    )
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "ACTIVE"

    allocated = client.post(
        f"/v1/runtime-sessions/{SESSION_ID}/resources",
        headers=AUTH_HEADERS,
        json={
            "allocation_id": "ALLOCATION-001",
            "capability_id": RESOURCE_CAPABILITY_ID,
            "resources": {
                "cpu_millis": 1000,
                "memory_mb": 1024,
                "gpu_millis": 0,
                "storage_mb": 100,
                "network_egress_mb": 100,
                "browser_slots": 1,
            },
        },
    )
    assert allocated.status_code == 201, allocated.text
    assert allocated.json()["status"] == "ACTIVE"


def test_instance_resource_limit_is_enforced(client: TestClient) -> None:
    seed_active_instance(client)
    client.post(
        "/v1/runtime-sessions", headers=AUTH_HEADERS, json=session_request()
    )
    response = client.post(
        f"/v1/runtime-sessions/{SESSION_ID}/resources",
        headers=AUTH_HEADERS,
        json={
            "allocation_id": "ALLOCATION-TOO-LARGE",
            "capability_id": RESOURCE_CAPABILITY_ID,
            "resources": {
                "cpu_millis": 3000,
                "memory_mb": 1024,
                "gpu_millis": 0,
                "storage_mb": 100,
                "network_egress_mb": 100,
                "browser_slots": 1,
            },
        },
    )
    assert response.status_code == 409
    assert "INSTANCE_RESOURCE_LIMIT_EXCEEDED" in response.json()["reason_codes"]


def test_node_capacity_is_enforced(client: TestClient) -> None:
    client.post(
        "/v1/runtime-nodes",
        headers=AUTH_HEADERS,
        json=node_request(
            capacity={
                "cpu_millis": 1000,
                "memory_mb": 1024,
                "gpu_millis": 0,
                "storage_mb": 1000,
                "network_egress_mb": 1000,
                "browser_slots": 1,
            }
        ),
    )
    response = client.post(
        "/v1/runtime-instances", headers=AUTH_HEADERS, json=instance_request()
    )
    assert response.status_code == 409
    assert "NODE_CAPACITY_EXCEEDED" in response.json()["reason_codes"]


def test_critical_health_requires_authorized_recovery(
    client: TestClient,
) -> None:
    seed_active_instance(client)
    response = client.post(
        f"/v1/runtime-instances/{INSTANCE_ID}/health",
        headers=AUTH_HEADERS,
        json={
            "state": "CRITICAL",
            "reported_by": "RUNTIME-HEALTH-MONITOR-001",
            "checks": {"evidence_writer": "FAILED"},
            "metrics": {"registry_latency_ms": 3000},
        },
    )
    assert response.status_code == 200, response.text
    instance = client.get(
        f"/v1/runtime-instances/{INSTANCE_ID}", headers=AUTH_HEADERS
    )
    assert instance.json()["status"] == "RECOVERY_PENDING"
    jobs = client.app.state.repository.recovery_jobs.values()
    job = next(iter(jobs))
    assert job.status == "AUTHORIZATION_REQUIRED"
    assert job.required_capability_action == "RUNTIME_RECOVERY_EXECUTE"


def test_termination_releases_resources_and_preserves_event_chain(
    client: TestClient,
) -> None:
    seed_active_instance(client)
    client.post(
        "/v1/runtime-sessions", headers=AUTH_HEADERS, json=session_request()
    )
    client.post(
        f"/v1/runtime-sessions/{SESSION_ID}/resources",
        headers=AUTH_HEADERS,
        json={
            "allocation_id": "ALLOCATION-001",
            "capability_id": RESOURCE_CAPABILITY_ID,
            "resources": {
                "cpu_millis": 1000,
                "memory_mb": 1024,
                "gpu_millis": 0,
                "storage_mb": 100,
                "network_egress_mb": 100,
                "browser_slots": 1,
            },
        },
    )
    terminated = client.post(
        f"/v1/runtime-sessions/{SESSION_ID}/terminate",
        headers=AUTH_HEADERS,
        json={"reason": "Actor ended session", "initiated_by": "DIGITALME-FAIZ-001"},
    )
    assert terminated.status_code == 200, terminated.text
    assert terminated.json()["status"] == "TERMINATED"
    allocation = client.app.state.repository.allocations["ALLOCATION-001"]
    assert allocation.status == "RELEASED"

    events = client.get(
        "/v1/runtime-events",
        headers=AUTH_HEADERS,
        params={"aggregate_type": "SESSION", "aggregate_id": SESSION_ID},
    ).json()
    assert [event["event_type"] for event in events] == [
        "RUNTIME_SESSION_STARTED",
        "RUNTIME_RESOURCES_ALLOCATED",
        "RUNTIME_SESSION_TERMINATED",
    ]
    assert events[0]["previous_event_hash"] is None
    assert events[1]["previous_event_hash"] == events[0]["evidence_hash"]
    assert events[2]["previous_event_hash"] == events[1]["evidence_hash"]


def test_openapi_operation_ids_and_security(client: TestClient) -> None:
    generated = client.get("/openapi.json").json()
    operation_ids = {
        operation["operationId"]
        for path in generated["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operation_ids == {
        "registerRuntimeNode",
        "provisionRuntimeInstance",
        "getRuntimeInstance",
        "attestRuntimeInstance",
        "createRuntimeSession",
        "allocateRuntimeResources",
        "reportRuntimeHealth",
        "terminateRuntimeSession",
        "listRuntimeEvents",
    }
    for path in generated["paths"].values():
        for method, operation in path.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation["security"] == [
                    {"mutualTLS": [], "bearerAuth": []}
                ]


def test_invalid_path_identifier_returns_problem_400(client: TestClient) -> None:
    response = client.get(
        "/v1/runtime-instances/not valid",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_codes"] == ["INVALID_REQUEST"]


def test_missing_server_token_is_configuration_error() -> None:
    from runtime_service.app import create_app
    from runtime_service.capabilities import InMemoryCapabilityVerifier
    from runtime_service.config import Settings
    from runtime_service.repository import InMemoryRuntimeRepository

    app = create_app(
        repository=InMemoryRuntimeRepository(),
        capability_verifier=InMemoryCapabilityVerifier(),
        settings=Settings(api_token=None),
    )
    with TestClient(app) as local_client:
        response = local_client.post(
            "/v1/runtime-nodes",
            headers={"X-Client-Cert-Verified": "SUCCESS"},
            json=node_request(),
        )
    assert response.status_code == 503
    assert response.json()["reason_codes"] == ["AUTH_CONFIGURATION_MISSING"]
