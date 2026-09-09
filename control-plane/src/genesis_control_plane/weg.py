from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.contracts import CapabilityTokenClaims, Command
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.tokens import TokenIssuer, TokenValidationError


class WEGValidationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ConsumedTokenLedger:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consumed_tokens (
                  token_id TEXT PRIMARY KEY,
                  command_id TEXT NOT NULL,
                  consumed_at TEXT NOT NULL
                )
                """
            )

    def is_consumed(self, token_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM consumed_tokens WHERE token_id = ?", (token_id,)
            ).fetchone()
        return row is not None

    def consume(self, token_id: str, command_id: str, consumed_at: datetime) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO consumed_tokens(token_id, command_id, consumed_at) VALUES (?, ?, ?)",
                    (token_id, command_id, consumed_at.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise WEGValidationError("REPLAY_DETECTED") from exc


class WardenExecutionGateway:
    def __init__(
        self,
        registry: AlphaRegistry,
        issuer: TokenIssuer,
        ledger: ConsumedTokenLedger,
    ):
        self._registry = registry
        self._issuer = issuer
        self._ledger = ledger

    def validate_and_consume(
        self, token: str, command: Command, now: datetime
    ) -> CapabilityTokenClaims:
        try:
            claims = self._issuer.decode_and_verify(token, now)
        except TokenValidationError as exc:
            raise WEGValidationError(exc.code) from exc

        checks = (
            (claims.command_id == command.command_id, "COMMAND_MISMATCH"),
            (claims.principal_id == command.principal_id, "PRINCIPAL_MISMATCH"),
            (claims.session_id == command.session_id, "SESSION_MISMATCH"),
            (claims.station_id == command.station_id, "STATION_MISMATCH"),
            (claims.adapter_id == command.adapter_id, "ADAPTER_MISMATCH"),
            (claims.target_resource_id == command.target_resource_id, "TARGET_MISMATCH"),
            (claims.capability == command.capability, "CAPABILITY_MISMATCH"),
            (
                claims.parameters_hash
                == sha256_hex(canonical_json(dict(command.parameters))),
                "PARAMETERS_MISMATCH",
            ),
        )
        for valid, code in checks:
            if not valid:
                raise WEGValidationError(code)

        if not self._registry.supports(
            command.target_resource_id, command.capability, command.adapter_id
        ):
            raise WEGValidationError("REGISTRY_BINDING_INVALID")

        self._ledger.consume(claims.token_id, command.command_id, now)
        return claims
