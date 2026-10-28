"""R0.4 provider-neutral, offline RS256 JWT verifier for DigitalMe-bound work.

This verifies an externally signed ACCESS token against operator-provisioned
JWKS. It does not mint tokens, fetch remote JWKS, act as an OIDC client, or
assert that a real DigitalMe issuer is configured.
"""
from __future__ import annotations

import base64
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
except ImportError:
    InvalidSignature = None

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")
_B64 = re.compile(r"^[A-Za-z0-9_-]+$")


class IdentityDenied(ValueError):
    pass


def _decode_b64(data: str) -> bytes:
    if not data or not _B64.fullmatch(data):
        raise IdentityDenied("IDENTITY_JWT_ENCODING_INVALID")
    try:
        return base64.b64decode(data + "=" * (-len(data) % 4), altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise IdentityDenied("IDENTITY_JWT_ENCODING_INVALID") from exc


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise IdentityDenied(f"IDENTITY_{label}_INVALID")
    return value


def _timestamp(value: Any, label: str) -> int:
    if type(value) is not int or not 0 < value < 4102444800:
        raise IdentityDenied(f"IDENTITY_{label}_INVALID")
    return value


@dataclass(frozen=True)
class IdentityContext:
    issuer: str
    subject: str
    tenant_id: str
    station_id: str
    source: str
    session_id: str
    token_id: str
    scopes: frozenset[str]
    expires_at: int

    @property
    def principal_id(self) -> str:
        return self.subject


class TokenRevocations:
    """Durable token/session revocation. Mutation belongs to trusted admin plane."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS revoked_token (
                issuer TEXT NOT NULL, token_id TEXT NOT NULL,
                revoked_at TEXT NOT NULL, PRIMARY KEY(issuer, token_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS revoked_session (
                issuer TEXT NOT NULL, session_id TEXT NOT NULL,
                revoked_at TEXT NOT NULL, PRIMARY KEY(issuer, session_id))""")

    def revoke_token(self, issuer: str, token_id: str) -> None:
        _id(token_id, "JTI")
        self._record("revoked_token", "token_id", issuer, token_id)

    def revoke_session(self, issuer: str, session_id: str) -> None:
        _id(session_id, "SESSION")
        self._record("revoked_session", "session_id", issuer, session_id)

    def _record(self, table: str, column: str, issuer: str, value: str) -> None:
        if not isinstance(issuer, str) or not issuer:
            raise IdentityDenied("IDENTITY_ISSUER_INVALID")
        with sqlite3.connect(self.path) as conn:
            conn.execute(f"INSERT OR IGNORE INTO {table}(issuer, {column}, revoked_at) VALUES (?, ?, ?)",
                         (issuer, value, datetime.now(timezone.utc).isoformat()))

    def revoked(self, issuer: str, jti: str, sid: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            for table, column, value in (("revoked_token", "token_id", jti),
                                         ("revoked_session", "session_id", sid)):
                if conn.execute(f"SELECT 1 FROM {table} WHERE issuer=? AND {column}=?",
                                (issuer, value)).fetchone():
                    return True
        return False


class DigitalMeAccessVerifier:
    """No discovery/network; trust only locally pinned public RSA keys."""

    def __init__(self, *, issuer: str, audience: str,
                 jwks: Mapping[str, Any], revocations: TokenRevocations):
        if InvalidSignature is None:
            raise RuntimeError("cryptography required for RS256 verification")
        if not isinstance(issuer, str) or not issuer.startswith("https://") or not issuer.rstrip("/") == issuer:
            raise IdentityDenied("IDENTITY_ISSUER_CONFIGURATION_INVALID")
        self.issuer = issuer
        self.audience = _id(audience, "AUDIENCE")
        self.revocations = revocations
        if not isinstance(jwks, Mapping) or not isinstance(jwks.get("keys"), list):
            raise IdentityDenied("IDENTITY_JWKS_INVALID")
        self.keys = {}
        for item in jwks["keys"]:
            if not isinstance(item, Mapping):
                raise IdentityDenied("IDENTITY_JWKS_INVALID")
            if item.get("kty") != "RSA" or item.get("alg", "RS256") != "RS256" or item.get("use", "sig") != "sig":
                raise IdentityDenied("IDENTITY_JWKS_INVALID")
            kid = _id(item.get("kid"), "KID")
            if kid in self.keys:
                raise IdentityDenied("IDENTITY_DUPLICATE_KID")
            try:
                n = int.from_bytes(_decode_b64(item["n"]), "big")
                e = int.from_bytes(_decode_b64(item["e"]), "big")
                if n.bit_length() < 2048 or e != 65537:
                    raise ValueError("weak key")
                key = rsa.RSAPublicNumbers(e, n).public_key()
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise IdentityDenied("IDENTITY_JWKS_INVALID") from exc
            self.keys[kid] = key
        if not self.keys:
            raise IdentityDenied("IDENTITY_JWKS_EMPTY")

    def verify(self, token: str, *, required_scope: str,
               now: datetime | None = None) -> IdentityContext:
        if not isinstance(token, str) or len(token) > 8192 or token.count(".") != 2:
            raise IdentityDenied("IDENTITY_TOKEN_MALFORMED")
        header_b64, body_b64, signature_b64 = token.split(".")
        try:
            header = json.loads(_decode_b64(header_b64))
            payload = json.loads(_decode_b64(body_b64))
        except (UnicodeError, ValueError) as exc:
            raise IdentityDenied("IDENTITY_TOKEN_MALFORMED") from exc
        if not isinstance(header, dict) or set(header) != {"alg", "typ", "kid"} or header.get("alg") != "RS256" or header.get("typ") != "JWT":
            raise IdentityDenied("IDENTITY_ALGORITHM_DENIED")
        kid = _id(header.get("kid"), "KID")
        if kid not in self.keys:
            raise IdentityDenied("IDENTITY_UNKNOWN_KID")
        if not isinstance(payload, dict):
            raise IdentityDenied("IDENTITY_CLAIMS_INVALID")
        signed = f"{header_b64}.{body_b64}".encode()
        try:
            self.keys[kid].verify(_decode_b64(signature_b64), signed,
                                  padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature as exc:
            raise IdentityDenied("IDENTITY_SIGNATURE_INVALID") from exc
        if payload.get("iss") != self.issuer or payload.get("aud") != self.audience:
            raise IdentityDenied("IDENTITY_ISSUER_AUDIENCE_DENIED")
        if payload.get("token_use") != "access":
            raise IdentityDenied("IDENTITY_ACCESS_TOKEN_REQUIRED")
        issued = _timestamp(payload.get("iat"), "IAT")
        not_before = _timestamp(payload.get("nbf"), "NBF")
        expiry = _timestamp(payload.get("exp"), "EXP")
        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise IdentityDenied("IDENTITY_CLOCK_INVALID")
        current = timestamp.timestamp()
        if issued > current + 60 or not_before > current + 60 or expiry <= current:
            raise IdentityDenied("IDENTITY_TOKEN_EXPIRED_OR_EARLY")
        if not_before < issued - 60 or expiry - issued > 900 or expiry <= issued:
            raise IdentityDenied("IDENTITY_TOKEN_LIFETIME_DENIED")
        sub = _id(payload.get("sub"), "SUBJECT")
        tenant = _id(payload.get("tenant_id"), "TENANT")
        station = _id(payload.get("station_id"), "STATION")
        source = _id(payload.get("source"), "SOURCE")
        sid = _id(payload.get("sid"), "SESSION")
        jti = _id(payload.get("jti"), "JTI")
        raw_scope = payload.get("scope")
        if not isinstance(raw_scope, str) or len(raw_scope) > 1024:
            raise IdentityDenied("IDENTITY_SCOPE_INVALID")
        scopes = frozenset(raw_scope.split())
        if required_scope not in scopes:
            raise IdentityDenied("IDENTITY_SCOPE_DENIED")
        if self.revocations.revoked(self.issuer, jti, sid):
            raise IdentityDenied("IDENTITY_TOKEN_REVOKED")
        return IdentityContext(self.issuer, sub, tenant, station, source, sid, jti, scopes, expiry)
