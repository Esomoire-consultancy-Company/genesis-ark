from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .auth import build_auth_dependency
from .capabilities import InMemoryCapabilityVerifier
from .config import Settings
from .engine import ControlTower
from .errors import ControlTowerError
from .models import (
    ApproveFleetCommandRequest,
    CompleteFleetCommandRequest,
    ControlTowerEvent,
    CreateFleetCommandRequest,
    DashboardSnapshot,
    DispatchFleetCommandRequest,
    FleetAsset,
    FleetCommand,
    Incident,
    IncidentActionRequest,
    ReportSignalRequest,
    UpsertFleetAssetRequest,
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
        resolved_verifier = (
            resolved_repository
            if resolved_settings.repository_backend == "postgres"
            else InMemoryCapabilityVerifier()
        )
    engine = ControlTower(resolved_repository, resolved_verifier, resolved_settings)
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

    app = FastAPI(
        title="Genesis Control Tower API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.repository = resolved_repository

    @app.exception_handler(ControlTowerError)
    async def control_tower_error_handler(_: Request, exc: ControlTowerError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.type_uri,
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
                "type": "urn:vsr:control-tower:request-validation-failed",
                "title": "Request Validation Failed",
                "status": 422,
                "detail": "The request did not satisfy the Control Tower contract",
                "reason_codes": ["REQUEST_VALIDATION_FAILED"],
                "errors": exc.errors(),
            },
            media_type="application/problem+json",
        )

    protected = [Depends(authenticate)]

    @app.post(
        "/v1/fleet/assets",
        response_model=FleetAsset,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
    )
    async def upsert_asset(request: UpsertFleetAssetRequest) -> FleetAsset:
        return await run_in_threadpool(engine.upsert_asset, request)

    @app.get("/v1/fleet/assets", response_model=list[FleetAsset], dependencies=protected)
    async def list_assets() -> list[FleetAsset]:
        return await run_in_threadpool(engine.list_assets)

    @app.get("/v1/fleet/assets/{asset_id}", response_model=FleetAsset, dependencies=protected)
    async def get_asset(asset_id: str) -> FleetAsset:
        return await run_in_threadpool(engine.get_asset, asset_id)

    @app.post(
        "/v1/signals",
        response_model=Incident,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=protected,
    )
    async def report_signal(request: ReportSignalRequest) -> Incident:
        return await run_in_threadpool(engine.report_signal, request)

    @app.get("/v1/incidents", response_model=list[Incident], dependencies=protected)
    async def list_incidents() -> list[Incident]:
        return await run_in_threadpool(engine.list_incidents)

    @app.post(
        "/v1/incidents/{incident_id}/acknowledge",
        response_model=Incident,
        dependencies=protected,
    )
    async def acknowledge_incident(
        incident_id: str,
        request: IncidentActionRequest,
    ) -> Incident:
        return await run_in_threadpool(engine.acknowledge_incident, incident_id, request)

    @app.post(
        "/v1/incidents/{incident_id}/resolve",
        response_model=Incident,
        dependencies=protected,
    )
    async def resolve_incident(
        incident_id: str,
        request: IncidentActionRequest,
    ) -> Incident:
        return await run_in_threadpool(engine.resolve_incident, incident_id, request)

    @app.post(
        "/v1/commands",
        response_model=FleetCommand,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
    )
    async def create_command(request: CreateFleetCommandRequest) -> FleetCommand:
        return await run_in_threadpool(engine.create_command, request)

    @app.get("/v1/commands", response_model=list[FleetCommand], dependencies=protected)
    async def list_commands() -> list[FleetCommand]:
        return await run_in_threadpool(engine.list_commands)

    @app.post(
        "/v1/commands/{command_id}/approve",
        response_model=FleetCommand,
        dependencies=protected,
    )
    async def approve_command(
        command_id: str,
        request: ApproveFleetCommandRequest,
    ) -> FleetCommand:
        return await run_in_threadpool(engine.approve_command, command_id, request)

    @app.post(
        "/v1/commands/{command_id}/dispatch",
        response_model=FleetCommand,
        dependencies=protected,
    )
    async def dispatch_command(
        command_id: str,
        request: DispatchFleetCommandRequest,
    ) -> FleetCommand:
        return await run_in_threadpool(engine.dispatch_command, command_id, request)

    @app.post(
        "/v1/commands/{command_id}/complete",
        response_model=FleetCommand,
        dependencies=protected,
    )
    async def complete_command(
        command_id: str,
        request: CompleteFleetCommandRequest,
    ) -> FleetCommand:
        return await run_in_threadpool(engine.complete_command, command_id, request)

    @app.get("/v1/dashboard", response_model=DashboardSnapshot, dependencies=protected)
    async def dashboard() -> DashboardSnapshot:
        return await run_in_threadpool(engine.dashboard)

    @app.get(
        "/v1/audit/{subject_id}",
        response_model=list[ControlTowerEvent],
        dependencies=protected,
    )
    async def audit(subject_id: str) -> list[ControlTowerEvent]:
        return await run_in_threadpool(engine.audit, subject_id)

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
