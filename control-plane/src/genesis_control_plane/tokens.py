from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import asdict
from datetime import datetime, timedelta

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.contracts import CapabilityTokenClaims, Command, Decision, DecisionResult


class TokenValidationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise TokenValidationError("MALFORMED_TOKEN") from exc


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise TokenValidationError("INVALID_TIME_CLAIM") from exc


class TokenIssuer:
    def __init__(self, secret: bytes, key_id: str, audience: str):
        if not secret:
            raise ValueError("secret must not be empty")
        self._secret = secret
        self._key_id = key_id
        self._audience = audience

    def issue(
        self,
        command: Command,
        decision: Decision,
        now: datetime,
        ttl_seconds: int = 60,
    ) -> str:
        if decision.result is not DecisionResult.PERMIT:
            raise TokenValidationError("DECISION_NOT_PERMIT")
        if decision.command_id != command.command_id:
            raise TokenValidationError("DECISION_COMMAND_MISMATCH")
        if ttl_seconds <= 0:
            raise TokenValidationError("INVALID_TTL")
        decision_expiry = _parse_time(decision.valid_until)
        expires_at = min(now + timedelta(seconds=ttl_seconds), decision_expiry)
        claims = CapabilityTokenClaims(
            token_id=f"WCT-{secrets.token_hex(8)}",
            decision_id=decision.decision_id,
            command_id=command.command_id,
            principal_id=command.principal_id,
            session_id=command.session_id,
            station_id=command.station_id,
            adapter_id=command.adapter_id,
            target_resource_id=command.target_resource_id,
            capability=command.capability,
            parameters_hash=sha256_hex(canonical_json(dict(command.parameters))),
            audience=self._audience,
            issued_at=now.isoformat(),
            not_before=now.isoformat(),
            expires_at=expires_at.isoformat(),
            max_uses=1,
            nonce=secrets.token_urlsafe(16),
            key_id=self._key_id,
        )
        payload = canonical_json(asdict(claims)).encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return f"{_b64url_encode(payload)}.{_b64url_encode(signature)}"

    def decode_and_verify(self, token: str, now: datetime) -> CapabilityTokenClaims:
        try:
            payload_part, signature_part = token.split(".", 1)
        except ValueError as exc:
            raise TokenValidationError("MALFORMED_TOKEN") from exc
        payload = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise TokenValidationError("INVALID_SIGNATURE")
        try:
            data = json.loads(payload.decode("utf-8"))
            claims = CapabilityTokenClaims(**data)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise TokenValidationError("INVALID_CLAIMS") from exc
        if claims.audience != self._audience:
            raise TokenValidationError("AUDIENCE_MISMATCH")
        if claims.max_uses != 1:
            raise TokenValidationError("INVALID_MAX_USES")
        if _parse_time(claims.not_before) > now:
            raise TokenValidationError("TOKEN_NOT_YET_VALID")
        if _parse_time(claims.expires_at) <= now:
            raise TokenValidationError("TOKEN_EXPIRED")
        return claims
