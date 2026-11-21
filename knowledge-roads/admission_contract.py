"""VSR-FOR-001 Phase 4: fail-closed registration / navigation admission contract.

SANDBOX adapter only. Does not create real Genesis registrations, Warden
execution authority, DigitalMe credentials or RiverOS receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class GateResult:
    disposition: str
    reason: str
    route_digest: str | None = None
    intent_digest: str | None = None
    authority_granted: bool = False
    execution_allowed: bool = False
    river_receipt_emitted: bool = False


def canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Mapping[str, Any]) -> str:
    return sha256(canonical(value)).hexdigest()


def prepare_route(route: Mapping[str, Any], registrations: Mapping[str, Any]) -> GateResult:
    """Validate a bounded route against a *supplied* registry projection.

    The projection is NOT an authenticated Genesis registry. Even a fully
    populated projection yields only READY_FOR_SANDBOX, never authority.
    """
    if route.get("capability") != "navigate.readonly":
        return GateResult("DENY", "CAPABILITY_NOT_ALLOWED")
    if route.get("execute") or route.get("mutation"):
        return GateResult("DENY", "EXECUTION_NOT_ALLOWED")
    required = ("route_id", "principal_id", "estate_id", "station_id", "purpose")
    if any(not isinstance(route.get(field), str) or not route[field].strip() for field in required):
        return GateResult("HOLD", "INCOMPLETE_ROUTE_CONTEXT")
    steps = route.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 24:
        return GateResult("DENY", "INVALID_ROUTE_LENGTH")
    if any(not isinstance(step, str) or not step.strip() for step in steps):
        return GateResult("DENY", "INVALID_FRAMEWORK_REFERENCE")
    if len(set(steps)) != len(steps):
        return GateResult("DENY", "DUPLICATE_FRAMEWORK_REFERENCE")
    qualified = []
    for step in steps:
        record = registrations.get(step)
        if not isinstance(record, Mapping) or record.get("registration_state") != "ACTIVE":
            return GateResult("HOLD", "FRAMEWORK_NOT_AUTHORITATIVELY_REGISTERED")
        stations = record.get("knowledge_station_ids")
        if not isinstance(stations, list) or not all(isinstance(s, str) for s in stations):
            return GateResult("HOLD", "MALFORMED_STATION_BINDING")
        if route["station_id"] not in stations:
            return GateResult("DENY", "KNOWLEDGE_STATION_SCOPE_MISMATCH")
        must_have = ("external_registry_id", "framework_version", "attestation_ref", "source_ref")
        if any(not isinstance(record.get(field), str) or not record[field].strip() for field in must_have):
            return GateResult("HOLD", "INCOMPLETE_REGISTRATION_PROVENANCE")
        if record.get("engine_qualification") == "EXECUTION_ONLY":
            return GateResult("DENY", "EXECUTION_ONLY_FRAMEWORK")
        qualified.append({"source_id": step, "genesis_id": record["external_registry_id"],
                          "version": record["framework_version"],
                          "attestation_ref": record["attestation_ref"],
                          "source_ref": record["source_ref"]})
    path = {key: route[key] for key in required}
    path["capability"] = "navigate.readonly"
    path["registered_steps"] = qualified
    intent = {key: route[key] for key in required}
    intent["capability"] = "navigate.readonly"
    intent["steps"] = list(steps)
    return GateResult("READY_FOR_SANDBOX", "TRUSTED_CONNECTORS_NOT_INSTALLED",
                      digest(path), digest(intent))


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def sign_sandbox_claims(claims: Mapping[str, Any], secret: bytes) -> str:
    """Fixture signature only: must never be trusted as a live Warden token."""
    return hmac.new(secret, canonical(claims), "sha256").hexdigest()


class SandboxWardenGate:
    """HMAC fixture verifier with in-memory replay protection; no real authority."""
    def __init__(self, fixture_secret: bytes):
        if not isinstance(fixture_secret, bytes) or len(fixture_secret) < 32:
            raise ValueError("Sandbox fixture secret must contain at least 32 bytes")
        self._secret = fixture_secret
        self._seen: set[str] = set()

    def assess(self, prepared: GateResult, route: Mapping[str, Any],
               claims: Mapping[str, Any], signature: str, now: datetime) -> GateResult:
        if prepared.disposition != "READY_FOR_SANDBOX" or not prepared.route_digest or not prepared.intent_digest:
            return GateResult("HOLD", "REGISTRATION_PREPARATION_INCOMPLETE")
        if route.get("execute") or route.get("mutation"):
            return GateResult("DENY", "EXECUTION_NOT_ALLOWED")
        keys = ("route_id", "principal_id", "estate_id", "station_id", "purpose")
        if any(not isinstance(route.get(key), str) for key in keys) or not isinstance(route.get("steps"), list):
            return GateResult("DENY", "ROUTE_CONTEXT_CHANGED")
        intent = {key: route[key] for key in keys}
        intent["capability"] = route.get("capability")
        intent["steps"] = route["steps"]
        if digest(intent) != prepared.intent_digest:
            return GateResult("DENY", "ROUTE_CONTEXT_CHANGED")
        if now.utcoffset() is None:
            return GateResult("DENY", "CLOCK_NOT_TIMEZONE_AWARE")
        if not isinstance(signature, str) or len(signature) != 64:
            return GateResult("DENY", "INVALID_SANDBOX_SIGNATURE")
        try:
            expected = sign_sandbox_claims(claims, self._secret)
        except (TypeError, ValueError):
            return GateResult("DENY", "MALFORMED_SANDBOX_CLAIMS")
        if not hmac.compare_digest(expected, signature):
            return GateResult("DENY", "INVALID_SANDBOX_SIGNATURE")
        required = {
            "audience": "vsr.knowledge-roads.sandbox", "capability": "navigate.readonly",
            "decision": "PERMIT", "policy_id": "VSR-NAV-READONLY-SANDBOX-R0.4",
            "route_digest": prepared.route_digest,
            "principal_id": route["principal_id"], "estate_id": route["estate_id"],
            "station_id": route["station_id"], "purpose": route["purpose"],
        }
        if any(claims.get(k) != v for k, v in required.items()):
            return GateResult("DENY", "SANDBOX_SCOPE_MISMATCH")
        issue = _aware_datetime(claims.get("issued_at"))
        expiry = _aware_datetime(claims.get("expires_at"))
        if issue is None or expiry is None or issue > now or expiry <= now:
            return GateResult("DENY", "SANDBOX_TIME_INVALID")
        duration = (expiry - issue).total_seconds()
        if not 0 < duration <= 120:
            return GateResult("DENY", "SANDBOX_TTL_INVALID")
        decision_id = claims.get("decision_id")
        nonce = claims.get("nonce")
        if not isinstance(decision_id, str) or not decision_id.strip() or not isinstance(nonce, str) or len(nonce) < 16:
            return GateResult("DENY", "SANDBOX_REPLAY_ID_INVALID")
        replay_id = decision_id + ":" + nonce
        if replay_id in self._seen:
            return GateResult("DENY", "SANDBOX_REPLAY_DENIED")
        self._seen.add(replay_id)
        return GateResult("SIMULATED_PERMIT", "SANDBOX_ONLY_NOT_LIVE_AUTHORITY", prepared.route_digest)
