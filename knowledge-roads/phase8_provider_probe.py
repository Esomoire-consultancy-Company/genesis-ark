"""VSR-FOR-001 R0.8: read-only HTTPS provider preflight, NOT admission.

Provider endpoints and public keys must be provisioned out of band by an
authorized staging operator. No provider is contacted unless a transport is
explicitly injected. This module verifies service metadata ONLY and never
registers objects, requests a Warden permit, or writes RiverOS evidence.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import ipaddress
import re
import secrets
import ssl
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROLES = ("GENESIS_REGISTRAR", "DIGITALME", "WARDEN", "RIVEROS")
PATH = "/.well-known/vsr/knowledge-roads"
DOMAIN = b"VSR-FOR-001-R08-PROVIDER-PREFLIGHT\0"
AUDIENCE = "vsr.knowledge-roads.staging-preflight"
HOST = re.compile(r"^(?=.{4,253}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_BODY = 32768


def canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _text(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 256 and bool(value.strip())


@dataclass(frozen=True)
class Provider:
    role: str
    url: str
    key_id: str
    issuer: str


@dataclass(frozen=True)
class HTTPResult:
    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class PreflightResult:
    disposition: str
    reason: str
    structurally_verified: tuple[str, ...] = ()
    provider_identity_operationally_attested: bool = False
    genesis_registration_performed: bool = False
    digitalme_authentication_performed: bool = False
    warden_authority_granted: bool = False
    river_receipt_emitted: bool = False
    engine_execution_allowed: bool = False
    release_allowed: bool = False


class Transport(Protocol):
    def get(self, url: str, headers: Mapping[str, str], timeout: float) -> HTTPResult: ...


class _NeverRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class HTTPSReadTransport:
    """Optional GET-only transport. Operator must separately enforce network egress.

    TLS certificates are verified by the supplied/default context; redirects
    are disabled. This is NOT an SSRF or DNS-rebinding defense by itself.
    """
    def __init__(self, context: ssl.SSLContext | None = None):
        self._opener = build_opener(HTTPSHandler(context=context or ssl.create_default_context()),
                                   _NeverRedirect())

    def get(self, url: str, headers: Mapping[str, str], timeout: float) -> HTTPResult:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with self._opener.open(request, timeout=timeout) as response:
                data = response.read(MAX_BODY + 1)
                return HTTPResult(response.status, response.headers.get("Content-Type", ""), data)
        except HTTPError as exc:
            return HTTPResult(exc.code, "", b"")


class ProviderPreflight:
    """Verifies four operator-configured service metadata responses only.

    Passing this preflight never means an identity, policy decision, route
    admission or RiverOS receipt has been verified. Production default is HOLD.
    """
    def __init__(self, providers: Mapping[str, Provider] | None = None,
                 anchors: Mapping[tuple[str, str], Ed25519PublicKey] | None = None,
                 approved_hosts: frozenset[str] | None = None,
                 transport: Transport | None = None):
        self.providers = dict(providers or {})
        self.anchors = dict(anchors or {})
        self.approved_hosts = frozenset(approved_hosts or ())
        self.transport = transport

    def _validate_configuration(self) -> str | None:
        if set(self.providers) != set(ROLES) or self.transport is None:
            return "PROVIDER_CONFIGURATION_OR_TRANSPORT_MISSING"
        if not self.approved_hosts:
            return "APPROVED_HOST_ALLOWLIST_MISSING"
        seen_urls: set[str] = set()
        seen_keys: set[bytes] = set()
        seen_issuers: set[str] = set()
        for role in ROLES:
            p = self.providers[role]
            if not isinstance(p, Provider) or p.role != role or not _text(p.issuer) or not _text(p.key_id):
                return "INVALID_PROVIDER_DEFINITION"
            try:
                parts = urlsplit(p.url)
                host, port = parts.hostname, parts.port
            except (ValueError, TypeError):
                return "INVALID_PROVIDER_URL"
            # A hostname allowlist cannot approve direct IP literals.
            if host is not None:
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    pass
                else:
                    return "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN"
                if host.endswith((".localhost", ".local", ".internal")):
                    return "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN"
            if (parts.scheme != "https" or host is None or host != host.lower()
                    or not HOST.fullmatch(host) or host not in self.approved_hosts
                    or port not in (None, 443) or parts.username is not None
                    or parts.password is not None or parts.path != PATH
                    or parts.query or parts.fragment):
                return "PROVIDER_URL_OUTSIDE_APPROVED_HTTPS_ORIGIN"
            if p.url in seen_urls or p.issuer in seen_issuers:
                return "PROVIDER_INDEPENDENCE_VIOLATION"
            seen_urls.add(p.url)
            seen_issuers.add(p.issuer)
            pub = self.anchors.get((role, p.key_id))
            if not isinstance(pub, Ed25519PublicKey):
                return "PINNED_PROVIDER_KEY_MISSING"
            raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
            if raw in seen_keys:
                return "PROVIDER_SIGNING_KEY_REUSED"
            seen_keys.add(raw)
        return None

    def inspect(self, *, commit_sha: str, now: datetime,
                nonce_source=None) -> PreflightResult:
        def stop(state: str, reason: str, seen=()) -> PreflightResult:
            return PreflightResult(state, reason, tuple(seen))

        if not isinstance(now, datetime) or now.utcoffset() is None:
            return stop("HOLD", "TRUSTED_CLOCK_REQUIRED")
        if not isinstance(commit_sha, str) or not SHA.fullmatch(commit_sha):
            return stop("HOLD", "BOUND_COMMIT_REQUIRED")
        configuration_error = self._validate_configuration()
        if configuration_error:
            return stop("HOLD", configuration_error)
        now = now.astimezone(timezone.utc)
        seen: list[str] = []
        for role in ROLES:
            p = self.providers[role]
            nonce = (nonce_source or (lambda: secrets.token_hex(24)))()
            if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{48}", nonce):
                return stop("DENY", "INVALID_CHALLENGE", seen)
            request_digest = sha256(canonical({
                "role": role, "endpoint": p.url, "nonce": nonce, "commit_sha": commit_sha
            })).hexdigest()
            headers = {
                "Accept": "application/json",
                "X-VSR-ReadOnly-Challenge": nonce,
                "X-VSR-Request-Digest": request_digest,
                "X-VSR-Commit": commit_sha,
                "Cache-Control": "no-store",
            }
            try:
                response = self.transport.get(p.url, headers, timeout=5.0)
            except Exception:
                return stop("HOLD", "PROVIDER_TRANSPORT_FAILED", seen)
            if not isinstance(response, HTTPResult) or response.status != 200:
                return stop("HOLD", "PROVIDER_DID_NOT_RETURN_200", seen)
            if response.content_type.split(";", 1)[0].strip().lower() != "application/json":
                return stop("DENY", "PROVIDER_CONTENT_TYPE_INVALID", seen)
            if not isinstance(response.body, bytes) or len(response.body) > MAX_BODY:
                return stop("DENY", "PROVIDER_BODY_TOO_LARGE", seen)
            try:
                data = json.loads(response.body)
            except (ValueError, UnicodeDecodeError):
                return stop("DENY", "PROVIDER_RESPONSE_NOT_JSON", seen)
            if not isinstance(data, dict) or data.get("role") != role or data.get("kid") != p.key_id or data.get("alg") != "Ed25519":
                return stop("DENY", "PROVIDER_ENVELOPE_MISMATCH", seen)
            payload, signature = data.get("payload"), data.get("signature")
            if not isinstance(payload, dict) or not isinstance(signature, str):
                return stop("DENY", "UNSIGNED_PROVIDER_METADATA", seen)
            if (payload.get("issuer") != p.issuer or payload.get("audience") != AUDIENCE
                    or payload.get("environment") != "staging"
                    or payload.get("capability") != "navigate.readonly"
                    or payload.get("classification") != "READONLY_SERVICE_METADATA"
                    or payload.get("status") != "AVAILABLE"
                    or payload.get("nonce") != nonce
                    or payload.get("request_digest") != request_digest
                    or payload.get("commit_sha") != commit_sha
                    or not _text(payload.get("service_version"))):
                return stop("DENY", "PROVIDER_METADATA_SCOPE_MISMATCH", seen)
            issued, expires = _date(payload.get("issued_at")), _date(payload.get("expires_at"))
            if (issued is None or expires is None or issued > now or expires <= now
                    or not 0 < (expires - issued).total_seconds() <= 120):
                return stop("DENY", "PROVIDER_METADATA_STALE", seen)
            try:
                raw = base64.b64decode(signature, altchars=b"-_", validate=True)
                if len(raw) != 64:
                    raise ValueError("wrong signature length")
                signed = {k: data[k] for k in ("role", "kid", "alg", "payload")}
                self.anchors[(role, p.key_id)].verify(raw, DOMAIN + canonical(signed))
            except (InvalidSignature, ValueError, KeyError, TypeError, OverflowError):
                return stop("DENY", "PROVIDER_SIGNATURE_INVALID", seen)
            seen.append(role)
        return stop("SIGNED_METADATA_PREFLIGHT_COMPLETE", "NO_OPERATIONAL_ATTESTATION_OR_AUTHORITY", seen)
