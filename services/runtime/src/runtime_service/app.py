from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Query, Request
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .auth import build_auth_dependency
from .capabilities import CapabilityVerifier, InMemoryCapabilityVerifier
from .config import Settings
from .engine import RuntimeManager
from .errors import RuntimeManagerError
from .models import (
    AllocateResourcesRequest,
    AttestInstanceRequest,
    CreateSessionRequest,
    HealthReportRequest,
    ProvisionInstanceRequest,
    RegisterNodeRequest,
    ResourceAllocation,
    RuntimeEvent,
    RuntimeHealthReport,
    RuntimeInstance,
    RuntimeNode,
    RuntimeSession,
    TerminateSessionRequest,
    Identifier,
)
from .repository import InMemoryRuntimeRepository, RuntimeRepository


def _build_components(
    settings: Settings,
) -> tuple[RuntimeRepository, CapabilityVerifier]:
    if settings.repository_backend == "memory":
        return InMemoryRuntimeRepository(), InMemoryCapabilityVerifier()
    if settings.repository_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError(
                "RUNTIME_MANAGER_DATABASE_URL is required when "
                "RUNTIME_MANAGER_REPOSITORY_BACKEND=postgres"
            )
        from .postgres_repository import PostgresRuntimeRepository

        repository = PostgresRuntimeRepository(
            settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            timeout=settings.database_pool_timeout_seconds,
            prepare_threshold=settings.database_prepare_threshold,
        )
        return repository, repository
    raise RuntimeError(
        f"Unsupported runtime repository backend: {settings.repository_backend}"
    )


def create_app(
    *,
    repository: RuntimeRepository | None = None,
    capability_verifier: CapabilityVerifier | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    if repository is None or capability_verifier is None:
        built_repository, built_verifier = _build_components(resolved_settings)
        resolved_repository = repository or built_repository
        resolved_verifier = capability_verifier or built_verifier
    else:
        resolved_repository = repository
        resolved_verifier = capability_verifier
    manager = RuntimeManager(
        resolved_repository,
        resolved_verifier,
        resolved_settings,
    )
    authenticate = build_auth_dependency(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        open_method = getattr(resolved_repository, "open", None)
        if open_method is not None:
            await run_in_threadpool(open_method)
        try:
            yield
        finally:
            close_method = getattr(resolved_repository, "close", None)
            if close_method is not None:
                await run_in_threadpool(close_method)

    app = FastAPI(
        lifespan=lifespan,
        title="Genesis Runtime Manager API",
        version="1.0.0",
        description=(
            "Capability-aware runtime provisioning, sessions, resource governance, "
            "health and durable runtime events."
        ),
    )
    app.state.repository = resolved_repository
    app.state.capability_verifier = resolved_verifier
    app.state.manager = manager

    @app.exception_handler(RuntimeManagerError)
    async def handle_runtime_error(
        request: Request,
        exc: RuntimeManagerError,
    ) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            headers=headers,
            content={
                "type": exc.type_uri,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url.path),
                "reason_codes": exc.reason_codes,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            media_type="application/problem+json",
            content={
                "type": "urn:vsr:runtime:invalid-request",
                "title": "Runtime request validation failed",
                "status": 400,
                "detail": "Request payload or parameters do not satisfy the runtime contract",
                "instance": str(request.url.path),
                "reason_codes": ["INVALID_REQUEST"],
                "errors": exc.errors(),
            },
        )

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schemes = schema.setdefault("components", {}).setdefault(
            "securitySchemes",
            {},
        )
        schemes["mutualTLS"] = {"type": "mutualTLS"}
        schemes["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        for path_item in schema.get("paths", {}).values():
            for method, operation in path_item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    operation["security"] = [
                        {"mutualTLS": [], "bearerAuth": []}
                    ]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "repository": resolved_settings.repository_backend,
        }

    @app.post(
        "/v1/runtime-nodes",
        operation_id="registerRuntimeNode",
        response_model=RuntimeNode,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    def register_node(payload: RegisterNodeRequest) -> RuntimeNode:
        return manager.register_node(payload)

    @app.post(
        "/v1/runtime-instances",
        operation_id="provisionRuntimeInstance",
        response_model=RuntimeInstance,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    def provision_instance(payload: ProvisionInstanceRequest) -> RuntimeInstance:
        return manager.provision_instance(payload)

    @app.get(
        "/v1/runtime-instances/{instanceId}",
        operation_id="getRuntimeInstance",
        response_model=RuntimeInstance,
        dependencies=[Depends(authenticate)],
    )
    def get_instance(instanceId: Identifier) -> RuntimeInstance:
        return manager.get_instance(instanceId)

    @app.post(
        "/v1/runtime-instances/{instanceId}/attest",
        operation_id="attestRuntimeInstance",
        response_model=RuntimeInstance,
        dependencies=[Depends(authenticate)],
    )
    def attest_instance(
        instanceId: Identifier,
        payload: AttestInstanceRequest,
    ) -> RuntimeInstance:
        return manager.attest_instance(instanceId, payload)

    @app.post(
        "/v1/runtime-sessions",
        operation_id="createRuntimeSession",
        response_model=RuntimeSession,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    def create_session(payload: CreateSessionRequest) -> RuntimeSession:
        return manager.create_session(payload)

    @app.post(
        "/v1/runtime-sessions/{sessionId}/resources",
        operation_id="allocateRuntimeResources",
        response_model=ResourceAllocation,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    def allocate_resources(
        sessionId: Identifier,
        payload: AllocateResourcesRequest,
    ) -> ResourceAllocation:
        return manager.allocate_resources(sessionId, payload)

    @app.post(
        "/v1/runtime-instances/{instanceId}/health",
        operation_id="reportRuntimeHealth",
        response_model=RuntimeHealthReport,
        dependencies=[Depends(authenticate)],
    )
    def report_health(
        instanceId: Identifier,
        payload: HealthReportRequest,
    ) -> RuntimeHealthReport:
        return manager.report_health(instanceId, payload)

    @app.post(
        "/v1/runtime-sessions/{sessionId}/terminate",
        operation_id="terminateRuntimeSession",
        response_model=RuntimeSession,
        dependencies=[Depends(authenticate)],
    )
    def terminate_session(
        sessionId: Identifier,
        payload: TerminateSessionRequest,
    ) -> RuntimeSession:
        return manager.terminate_session(sessionId, payload)

    @app.get(
        "/v1/runtime-events",
        operation_id="listRuntimeEvents",
        response_model=list[RuntimeEvent],
        dependencies=[Depends(authenticate)],
    )
    def list_events(
        aggregate_type: str = Query(min_length=1),
        aggregate_id: Identifier = Query(),
    ) -> list[RuntimeEvent]:
        return resolved_repository.list_events(aggregate_type, aggregate_id)

    return app


app = create_app()
