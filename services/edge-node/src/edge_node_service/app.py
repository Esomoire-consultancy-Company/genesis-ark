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
from .engine import EdgeNodeEngine
from .errors import EdgeNodeError
from .models import (
    CommandLease,
    CompleteCommandRequest,
    EdgeCommand,
    EdgeEvidenceEvent,
    EdgeNodeIdentity,
    EnrollNodeRequest,
    HeartbeatReceipt,
    HeartbeatRequest,
    IssueCommandRequest,
    LeaseCommandRequest,
    SpoolFlushReceipt,
    SpoolFlushRequest,
)
from .repository import InMemoryEdgeNodeRepository
from .signatures import UnavailableSecretResolver


def create_app(
    settings: Settings | None = None,
    repository=None,
    capability_verifier=None,
    secret_resolver=None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_repository = repository
    if resolved_repository is None:
        if resolved_settings.repository_backend == "postgres":
            from .postgres_repository import PostgresEdgeNodeRepository

            resolved_repository = PostgresEdgeNodeRepository(
                resolved_settings.database_url or "",
                min_size=resolved_settings.database_pool_min_size,
                max_size=resolved_settings.database_pool_max_size,
                timeout=resolved_settings.database_pool_timeout_seconds,
                prepare_threshold=resolved_settings.database_prepare_threshold,
            )
        else:
            resolved_repository = InMemoryEdgeNodeRepository()
    resolved_verifier = capability_verifier
    if resolved_verifier is None:
        if resolved_settings.repository_backend == "postgres":
            resolved_verifier = resolved_repository
        else:
            resolved_verifier = InMemoryCapabilityVerifier()
    resolved_secret_resolver = secret_resolver or UnavailableSecretResolver()
    engine = EdgeNodeEngine(
        resolved_repository,
        resolved_verifier,
        resolved_secret_resolver,
        resolved_settings,
    )
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
        title="Genesis Edge Node API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.repository = resolved_repository

    @app.exception_handler(EdgeNodeError)
    async def edge_error_handler(_: Request, exc: EdgeNodeError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"urn:genesis:edge-node:{exc.reason_codes[0].lower()}",
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
                "type": "urn:genesis:edge-node:request-validation-failed",
                "title": "Request Validation Failed",
                "status": 422,
                "detail": "The request did not satisfy the Edge Node contract",
                "reason_codes": ["REQUEST_VALIDATION_FAILED"],
                "errors": exc.errors(),
            },
            media_type="application/problem+json",
        )

    @app.post(
        "/v1/edge-nodes/enroll",
        response_model=EdgeNodeIdentity,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def enroll(request: EnrollNodeRequest) -> EdgeNodeIdentity:
        return await run_in_threadpool(engine.enroll, request)

    @app.post(
        "/v1/edge-nodes/{node_id}/heartbeats",
        response_model=HeartbeatReceipt,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(authenticate)],
    )
    async def heartbeat(node_id: str, request: HeartbeatRequest) -> HeartbeatReceipt:
        return await run_in_threadpool(engine.heartbeat, node_id, request)

    @app.post(
        "/v1/edge-nodes/{node_id}/commands",
        response_model=EdgeCommand,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def issue_command(node_id: str, request: IssueCommandRequest) -> EdgeCommand:
        return await run_in_threadpool(engine.issue_command, node_id, request)

    @app.post(
        "/v1/edge-nodes/{node_id}/commands/lease",
        response_model=CommandLease | None,
        dependencies=[Depends(authenticate)],
    )
    async def lease_command(node_id: str, request: LeaseCommandRequest) -> CommandLease | None:
        return await run_in_threadpool(engine.lease_command, node_id, request)

    @app.post(
        "/v1/edge-nodes/{node_id}/commands/{command_id}/complete",
        response_model=EdgeCommand,
        dependencies=[Depends(authenticate)],
    )
    async def complete_command(
        node_id: str,
        command_id: str,
        request: CompleteCommandRequest,
    ) -> EdgeCommand:
        return await run_in_threadpool(engine.complete_command, node_id, command_id, request)

    @app.post(
        "/v1/edge-nodes/{node_id}/spool/flush",
        response_model=SpoolFlushReceipt,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(authenticate)],
    )
    async def flush_spool(node_id: str, request: SpoolFlushRequest) -> SpoolFlushReceipt:
        return await run_in_threadpool(engine.ingest_spool, node_id, request)

    @app.get(
        "/v1/edge-nodes/{node_id}",
        response_model=EdgeNodeIdentity,
        dependencies=[Depends(authenticate)],
    )
    async def get_identity(node_id: str) -> EdgeNodeIdentity:
        return await run_in_threadpool(engine.get_identity, node_id)

    @app.get(
        "/v1/edge-nodes/{node_id}/evidence",
        response_model=list[EdgeEvidenceEvent],
        dependencies=[Depends(authenticate)],
    )
    async def list_evidence(node_id: str) -> list[EdgeEvidenceEvent]:
        return await run_in_threadpool(engine.list_events, node_id)

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
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
