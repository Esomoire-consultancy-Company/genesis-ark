"""HTTP intake boundary for the Genesis ARK Cloud Gateway R0.1.

This service does NOT remotely execute Docker, mint Warden permits, register
members, settle money, or accept client-provided authority decisions.
"""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from genesis_gateway.ledger import CapacityExceeded, IntentConflict, PostgresLedger

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    issuer_id: str = ""
    database_url: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("GENESIS_GATEWAY_API_KEY", ""),
            issuer_id=os.getenv("GENESIS_GATEWAY_ISSUER_ID", ""),
            database_url=os.getenv("DATABASE_URL", ""),
        )

    def complete(self) -> bool:
        return (
            len(self.api_key) >= 32
            and bool(self.issuer_id.strip())
            and self.database_url.startswith(("postgresql://", "postgres://"))
        )


Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    correlation_id: Identifier
    target_resource_id: Identifier
    capability: Identifier


class Receipt(BaseModel):
    request_id: str
    event_id: str
    result: str
    reason_code: str
    evidence_hash: str
    previous_hash: str | None
    execution_invoked: bool


def create_app(settings: Settings | None = None, ledger=None) -> FastAPI:
    cfg = settings if settings is not None else Settings.from_env()
    store = ledger if ledger is not None else (PostgresLedger(cfg.database_url) if cfg.database_url else None)
    app = FastAPI(title="Genesis ARK Cloud Gateway", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz():
        return {"status": "alive", "revision": "R0.1", "execution_enabled": False}

    @app.get("/readyz")
    def readyz():
        if not cfg.complete() or store is None:
            raise HTTPException(503, detail="GATEWAY_NOT_PROVISIONED")
        try:
            if not store.ready():
                raise HTTPException(503, detail="EVIDENCE_SCHEMA_NOT_READY")
        except HTTPException:
            raise
        except Exception as exc:
            # Never log driver exceptions: some can include connection secrets.
            logger.error("Gateway readiness failure: %s", type(exc).__name__)
            raise HTTPException(503, detail="EVIDENCE_UNAVAILABLE") from None
        return {"status": "ready", "mode": "deny-only", "execution_enabled": False}

    @app.post("/v1/intents", response_model=Receipt)
    def submit_intent(intent: Intent, authorization: str | None = Header(default=None)):
        if not cfg.complete() or store is None:
            raise HTTPException(503, detail="GATEWAY_NOT_PROVISIONED")
        expected = "Bearer " + cfg.api_key
        if not authorization or not hmac.compare_digest(authorization.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(401, detail="UNAUTHENTICATED", headers={"WWW-Authenticate": "Bearer"})

        request = intent.model_dump(mode="json")
        try:
            # Health alone never authorizes intake. Enforce the database
            # migration/privilege readiness gate on every authenticated write.
            if not store.ready():
                raise HTTPException(503, detail="EVIDENCE_SCHEMA_NOT_READY")
            return store.record_denial(request, cfg.issuer_id)
        except HTTPException:
            raise
        except IntentConflict:
            raise HTTPException(409, detail="REQUEST_ID_CONFLICT") from None
        except CapacityExceeded as exc:
            if exc.reason == "INTENT_RATE_LIMIT":
                raise HTTPException(429, detail=exc.reason,
                                    headers={"Retry-After": "60"}) from None
            raise HTTPException(503, detail="EVIDENCE_SPOOL_FULL") from None
        except Exception as exc:
            # Never return a receipt for a failed evidence write; log no secrets.
            logger.error("Gateway evidence write failure: %s", type(exc).__name__)
            raise HTTPException(503, detail="EVIDENCE_UNAVAILABLE") from None

    return app


app = create_app()
