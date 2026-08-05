from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .auth import build_auth_dependency
from .config import Settings
from .engine import CloudBrowserEngine
from .errors import CloudBrowserError
from .executor import BrowserExecutor, DeterministicBrowserExecutor
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


def create_app(
    *,
    repository: CloudBrowserRepository | None = None,
    warden: WardenClient | None = None,
    executor: BrowserExecutor | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_repository = repository or InMemoryCloudBrowserRepository()
    resolved_warden = warden or HttpWardenClient(resolved_settings)
    resolved_executor = executor or DeterministicBrowserExecutor()
    engine = CloudBrowserEngine(
        resolved_repository,
        resolved_warden,
        resolved_executor,
        resolved_settings,
    )
    authenticate = build_auth_dependency(resolved_settings)

    app = FastAPI(
        title="Genesis Governed CloudBrowser API",
        version="1.0.0",
        description="Warden-gated browser session and action broker for Genesis Actor Boxes.",
    )
    app.state.repository = resolved_repository
    app.state.engine = engine

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
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes["mutualTLS"] = {"type": "mutualTLS"}
        schemes["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        for path_item in schema.get("paths", {}).values():
            for method, operation in path_item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    operation["security"] = [{"mutualTLS": [], "bearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/browser-sessions",
        operation_id="createGovernedBrowserSession",
        response_model=BrowserSession,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    async def create_session(payload: BrowserSessionRequest) -> BrowserSession:
        return engine.create_session(payload)

    @app.get(
        "/v1/browser-sessions/{sessionId}",
        operation_id="getGovernedBrowserSession",
        response_model=BrowserSession,
        dependencies=[Depends(authenticate)],
    )
    async def get_session(sessionId: str) -> BrowserSession:
        return engine.get_session(sessionId)

    @app.post(
        "/v1/browser-sessions/{sessionId}/actions/evaluate",
        operation_id="evaluateGovernedBrowserAction",
        response_model=BrowserAction,
        dependencies=[Depends(authenticate)],
    )
    async def evaluate_action(
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
    async def approve_action(
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
    async def pause_session(
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
    async def terminate_session(
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
    async def get_evidence(sessionId: str) -> list[EvidenceEvent]:
        return engine.evidence(sessionId)

    @app.get(
        "/v1/browser-sessions/{sessionId}/usage",
        operation_id="getGovernedBrowserUsage",
        response_model=UsageRecord,
        dependencies=[Depends(authenticate)],
    )
    async def get_usage(sessionId: str) -> UsageRecord:
        return engine.usage(sessionId)

    return app


app = create_app()
