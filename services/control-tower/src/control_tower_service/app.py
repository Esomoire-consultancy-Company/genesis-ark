from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .auth import build_auth_dependency
from .capabilities import InMemoryCapabilityVerifier
from .config import Settings
from .engine import ControlTowerEngine
from .errors import ControlTowerError
from .models import (
    AuthorizeCommandRequest,
    ControlCommandRequest,
    ControlIncident,
    CreateCommandRequest,
    CreateIncidentRequest,
    DashboardSummary,
    DispatchCommandRequest,
    FleetNodeSnapshot,
    FleetRefreshReceipt,
    FleetRefreshRequest,
    FleetStatus,
    IncidentStatus,
    IncidentTransitionRequest,
    PublicationAckRequest,
    PublicationLease,
    PublicationLeaseRequest,
    PublicationReceipt,
)
from .repository import InMemoryControlTowerRepository


def create_app(
    settings: Settings | None = None,
    repository=None,
    capability_verifier=None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_repository = repository
    if resolved_repository is None:
        if resolved_settings.repository_backend == "postgres":
            from .postgres_repository import PostgresControlTowerRepository

            resolved_repository = PostgresControlTowerRepository(
                resolved_settings.database_url or "",
                min_size=resolved_settings.database_pool_min_size,
                max_size=resolved_settings.database_pool_max_size,
                timeout=resolved_settings.database_pool_timeout_seconds,
                prepare_threshold=resolved_settings.database_prepare_threshold,
            )
        else:
            resolved_repository = InMemoryControlTowerRepository()
    resolved_verifier = capability_verifier
    if resolved_verifier is None:
        if resolved_settings.repository_backend == "postgres":
            resolved_verifier = resolved_repository
        else:
            resolved_verifier = InMemoryCapabilityVerifier()
    engine = ControlTowerEngine(resolved_repository, resolved_verifier, resolved_settings)
    authenticate = build_auth_dependency(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        open_method = getattr(resolved_repository, "open", None)
        close_method = getattr(resolved_repository, "close", None)
        if callable(open_method):
            await run_in_threadpool(open_method)
        try:
            yield
        finally:
            if callable(close_method):
                await run_in_threadpool(close_method)

    app = FastAPI(title="Genesis Control Tower API", version="1.0.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.repository = resolved_repository

    @app.exception_handler(ControlTowerError)
    async def control_error_handler(_: Request, exc: ControlTowerError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"urn:genesis:control-tower:{exc.reason_codes[0].lower()}",
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "reason_codes": exc.reason_codes,
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "type": "urn:genesis:control-tower:request-validation-failed",
                "title": "Request Validation Failed",
                "status": 422,
                "detail": "The request did not satisfy the Control Tower contract",
                "reason_codes": ["REQUEST_VALIDATION_FAILED"],
                "errors": exc.errors(),
            },
            media_type="application/problem+json",
        )

    dependencies = [Depends(authenticate)]

    @app.post("/v1/control-tower/fleet/refresh", response_model=FleetRefreshReceipt, dependencies=dependencies)
    async def refresh_fleet(request: FleetRefreshRequest) -> FleetRefreshReceipt:
        return await run_in_threadpool(engine.refresh_fleet, request.actor_id)

    @app.get("/v1/control-tower/fleet", response_model=list[FleetNodeSnapshot], dependencies=dependencies)
    async def list_fleet(status_filter: FleetStatus | None = Query(default=None, alias="status")) -> list[FleetNodeSnapshot]:
        return await run_in_threadpool(engine.list_fleet, status_filter)

    @app.get("/v1/control-tower/nodes/{node_id}", response_model=FleetNodeSnapshot, dependencies=dependencies)
    async def get_node(node_id: str) -> FleetNodeSnapshot:
        return await run_in_threadpool(engine.get_node, node_id)

    @app.post(
        "/v1/control-tower/command-requests",
        response_model=ControlCommandRequest,
        status_code=status.HTTP_201_CREATED,
        dependencies=dependencies,
    )
    async def create_command(request: CreateCommandRequest) -> ControlCommandRequest:
        return await run_in_threadpool(engine.create_command_request, request)

    @app.post(
        "/v1/control-tower/command-requests/{request_id}/authorize",
        response_model=ControlCommandRequest,
        dependencies=dependencies,
    )
    async def authorize_command(request_id: str, request: AuthorizeCommandRequest) -> ControlCommandRequest:
        return await run_in_threadpool(engine.authorize_command, request_id, request)

    @app.post(
        "/v1/control-tower/command-requests/{request_id}/dispatch",
        response_model=ControlCommandRequest,
        dependencies=dependencies,
    )
    async def dispatch_command(request_id: str, request: DispatchCommandRequest) -> ControlCommandRequest:
        return await run_in_threadpool(engine.dispatch_command, request_id, request)

    @app.post(
        "/v1/control-tower/incidents",
        response_model=ControlIncident,
        status_code=status.HTTP_201_CREATED,
        dependencies=dependencies,
    )
    async def create_incident(request: CreateIncidentRequest) -> ControlIncident:
        return await run_in_threadpool(engine.create_incident, request)

    @app.post(
        "/v1/control-tower/incidents/{incident_id}/transition",
        response_model=ControlIncident,
        dependencies=dependencies,
    )
    async def transition_incident(incident_id: str, request: IncidentTransitionRequest) -> ControlIncident:
        return await run_in_threadpool(engine.transition_incident, incident_id, request)

    @app.get("/v1/control-tower/incidents", response_model=list[ControlIncident], dependencies=dependencies)
    async def list_incidents(status_filter: IncidentStatus | None = Query(default=None, alias="status")) -> list[ControlIncident]:
        return await run_in_threadpool(engine.list_incidents, status_filter)

    @app.post("/v1/control-tower/publications/lease", response_model=PublicationLease, dependencies=dependencies)
    async def lease_publications(request: PublicationLeaseRequest) -> PublicationLease:
        return await run_in_threadpool(engine.lease_publications, request)

    @app.post(
        "/v1/control-tower/publications/{lease_id}/ack",
        response_model=PublicationReceipt,
        dependencies=dependencies,
    )
    async def acknowledge_publications(lease_id: str, request: PublicationAckRequest) -> PublicationReceipt:
        return await run_in_threadpool(engine.acknowledge_publications, lease_id, request)

    @app.get("/v1/control-tower/dashboard", response_model=DashboardSummary, dependencies=dependencies)
    async def dashboard() -> DashboardSummary:
        return await run_in_threadpool(engine.dashboard)

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
            {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
                "mutualTLS": {"type": "mutualTLS"},
            }
        )
        for path in schema.get("paths", {}).values():
            for operation in path.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"bearerAuth": [], "mutualTLS": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
    return app
