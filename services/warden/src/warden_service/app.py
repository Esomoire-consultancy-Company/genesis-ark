from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .auth import build_auth_dependency
from .config import Settings
from .engine import WardenEngine
from .errors import WardenError
from .models import (
    BoxControlState,
    BoxLockRequest,
    CapabilityGrant,
    CapabilityIssueRequest,
    PolicyDecision,
    PolicyDecisionRequest,
    Revocation,
    RevocationRequest,
)
from .repository import InMemoryRegistry, RegistryRepository


def create_app(
    *,
    registry: RegistryRepository | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_registry = registry or InMemoryRegistry()
    engine = WardenEngine(resolved_registry, resolved_settings)
    authenticate = build_auth_dependency(resolved_settings)

    app = FastAPI(
        title="Warden Actor Box Control API",
        version="1.0.0",
        description="Deny-by-default control plane for Genesis Actor Boxes.",
    )
    app.state.registry = resolved_registry
    app.state.engine = engine

    @app.exception_handler(WardenError)
    async def handle_warden_error(
        request: Request,
        exc: WardenError,
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
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/policy-decisions/evaluate",
        operation_id="evaluateActorBoxPolicy",
        response_model=PolicyDecision,
        dependencies=[Depends(authenticate)],
    )
    async def evaluate_policy(
        payload: PolicyDecisionRequest,
    ) -> PolicyDecision:
        return engine.evaluate(payload)

    @app.post(
        "/v1/capabilities/issue",
        operation_id="issueActorBoxCapability",
        response_model=CapabilityGrant,
        status_code=201,
        dependencies=[Depends(authenticate)],
    )
    async def issue_capability(
        payload: CapabilityIssueRequest,
    ) -> CapabilityGrant:
        return engine.issue_capability(payload)

    @app.post(
        "/v1/capabilities/{capabilityId}/revoke",
        operation_id="revokeActorBoxCapability",
        response_model=Revocation,
        dependencies=[Depends(authenticate)],
    )
    async def revoke_capability(
        capabilityId: str,
        payload: RevocationRequest,
    ) -> Revocation:
        return engine.revoke_capability(capabilityId, payload)

    @app.post(
        "/v1/boxes/{boxId}/lock",
        operation_id="lockActorBox",
        response_model=BoxControlState,
        dependencies=[Depends(authenticate)],
    )
    async def lock_box(
        boxId: str,
        payload: BoxLockRequest,
    ) -> BoxControlState:
        return engine.lock_box(boxId, payload)

    @app.get(
        "/v1/boxes/{boxId}/control-state",
        operation_id="getActorBoxControlState",
        response_model=BoxControlState,
        dependencies=[Depends(authenticate)],
    )
    async def get_control_state(boxId: str) -> BoxControlState:
        return engine.control_state(boxId)

    return app


app = create_app()
