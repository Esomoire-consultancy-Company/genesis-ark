from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .auth import build_auth_dependency
from .config import Settings
from .engine import CloudBrowserEngine
from .errors import CloudBrowserError
from .executor import (
    BrowserExecutor,
    DeterministicBrowserExecutor,
    PlaywrightChromiumExecutor,
)
from .models import (
    BrowserAction,
    BrowserActionRequest,
    BrowserApprovalRequest,
    BrowserSession,
    BrowserSessionRequest,
    EvidenceEvent,
    SessionPauseRequest,
    SessionTerminateRequest,
    UsageRecord,
)
from .repository import CloudBrowserRepository, InMemoryCloudBrowserRepository
from .warden_client import HttpWardenClient, WardenClient


def _build_repository(settings: Settings) -> CloudBrowserRepository:
    if settings.repository_backend == "memory":
        return InMemoryCloudBrowserRepository()
    if settings.repository_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError(
                "CLOUDBROWSER_DATABASE_URL is required when "
                "CLOUDBROWSER_REPOSITORY_BACKEND=postgres"
            )
        from .postgres_repository import PostgresCloudBrowserRepository

        return PostgresCloudBrowserRepository(
            settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            timeout=settings.database_pool_timeout_seconds,
            prepare_threshold=settings.database_prepare_threshold,
        )
    raise RuntimeError(
        f"Unsupported CloudBrowser repository backend: {settings.repository_backend}"
    )


def _build_executor(settings: Settings) -> BrowserExecutor:
    if settings.executor_mode == "DETERMINISTIC":
        return DeterministicBrowserExecutor()
    if settings.executor_mode == "PLAYWRIGHT":
        return PlaywrightChromiumExecutor(
            chromium_executable=settings.chromium_executable,
            headless=settings.chromium_headless,
            quarantine_root=settings.quarantine_root,
            timeout_seconds=settings.executor_timeout_seconds,
        )
    raise RuntimeError(f"Unsupported CloudBrowser executor: {settings.executor_mode}")


def create_app(
    *,
    repository: CloudBrowserRepository | None = None,
    warden: WardenClient | None = None,
    executor: BrowserExecutor | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_repository = repository or _build_repository(resolved_settings)
    resolved_warden = warden or HttpWardenClient(resolved_settings)
    resolved_executor = executor or _build_executor(resolved_settings)
    engine = CloudBrowserEngine(
        resolved_repository,
        resolved_warden,
        resolved_executor,
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
            await run_in_threadpool(resolved_executor.close)
            close_method = getattr(resolved_repository, "close", None)
            if close_method is not None:
                await run_in_threadpool(close_method)

    app = FastAPI(
        lifespan=lifespan,
        title="Genesis Governed CloudBrowser API",
        version="1.1.0",
        description="Warden-gated browser session and action broker for Genesis Actor Boxes.",
    )
    app.state.repository = resolved_repository
    app.state.engine = engine
    app.state.executor = resolved_executor

    @app.exception_handler(CloudBrowserError)
    async def handle_cloudbrowser_error(
        request: Request,
        exc: CloudBrowserError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content={
                "type": exc.type_uri,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url.path),
                "reason_codes": exc.reason_codes,
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
            "securitySchemes", {}
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
            "executor": resolved_settings.executor_mode,
        }

    @app.post(
        "/v1/browser-sessions",
        operation_id="createGovernedBrowserSession",
        response_model=BrowserSession,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    def create_session(payload: BrowserSessionRequest) -> BrowserSession:
        return engine.create_session(payload)

    @app.get(
        "/v1/browser-sessions/{sessionId}",
        operation_id="getGovernedBrowserSession",
        response_model=BrowserSession,
        dependencies=[Depends(authenticate)],
    )
    def get_session(sessionId: str) -> BrowserSession:
        return engine.get_session(sessionId)

    @app.post(
        "/v1/browser-sessions/{sessionId}/actions/evaluate",
        operation_id="evaluateGovernedBrowserAction",
        response_model=BrowserAction,
        dependencies=[Depends(authenticate)],
    )
    def evaluate_action(
        sessionId: str,
        payload: BrowserActionRequest,
    ) -> BrowserAction:
        return engine.evaluate_action(sessionId, payload)

    @app.post(
        "/v1/browser-sessions/{sessionId}/approve",
        operation_id="approveGovernedBrowserAction",
        response_model=BrowserAction,
        dependencies=[Depends(authenticate)],
    )
    def approve_action(
        sessionId: str,
        payload: BrowserApprovalRequest,
    ) -> BrowserAction:
        return engine.approve_action(sessionId, payload)

    @app.post(
        "/v1/browser-sessions/{sessionId}/pause",
        operation_id="pauseGovernedBrowserSession",
        response_model=BrowserSession,
        dependencies=[Depends(authenticate)],
    )
    def pause_session(
        sessionId: str,
        payload: SessionPauseRequest,
    ) -> BrowserSession:
        return engine.pause_session(sessionId, payload)

    @app.post(
        "/v1/browser-sessions/{sessionId}/terminate",
        operation_id="terminateGovernedBrowserSession",
        response_model=BrowserSession,
        dependencies=[Depends(authenticate)],
    )
    def terminate_session(
        sessionId: str,
        payload: SessionTerminateRequest,
    ) -> BrowserSession:
        return engine.terminate_session(sessionId, payload)

    @app.get(
        "/v1/browser-sessions/{sessionId}/evidence",
        operation_id="getGovernedBrowserEvidence",
        response_model=list[EvidenceEvent],
        dependencies=[Depends(authenticate)],
    )
    def get_evidence(sessionId: str) -> list[EvidenceEvent]:
        return engine.evidence(sessionId)

    @app.get(
        "/v1/browser-sessions/{sessionId}/usage",
        operation_id="getGovernedBrowserUsage",
        response_model=UsageRecord,
        dependencies=[Depends(authenticate)],
    )
    def get_usage(sessionId: str) -> UsageRecord:
        return engine.usage(sessionId)

    return app


app = create_app()
