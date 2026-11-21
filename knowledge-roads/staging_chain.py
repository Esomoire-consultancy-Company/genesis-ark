"""VSR-FOR-001 R0.5: staged navigation integration contract.

ALL inputs from adapters are untrusted fixtures in this module. The strongest
result is STAGING_PREVIEW_ACCEPTED; this module can never grant authority,
execute engines, or issue an authentic RiverOS evidence receipt.

An authenticated production implementation must use separately reviewed
verifier-backed adapters, durable replay prevention and a real RiverOS writer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol


ALLOWED_CAPABILITY = "navigate.readonly"
REQUIRED_TEXT = ("request_id", "principal_id", "session_id", "estate_id", "station_id", "location_id", "purpose")


class RegistrarPort(Protocol):
    def resolve(self, framework_ids: tuple[str, ...], station_id: str) -> Mapping[str, Mapping[str, Any]]: ...


class IdentityPort(Protocol):
    def verify(self, intent: Mapping[str, Any]) -> Mapping[str, Any]: ...


class WardenPort(Protocol):
    def evaluate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class RiverPort(Protocol):
    def acknowledge(self, event: Mapping[str, Any]) -> Mapping[str, Any]: ...


class ReplayPort(Protocol):
    def reserve(self, decision_id: str) -> bool: ...


@dataclass(frozen=True)
class StageOutcome:
    disposition: str
    reason: str
    route_digest: str | None = None
    simulated_evidence_ack: bool = False
    external_authority_granted: bool = False
    engine_execution_allowed: bool = False
    river_receipt_emitted: bool = False


class MemoryFixtureReplay:
    """Non-durable, non-production replay simulation."""
    def __init__(self) -> None:
        self._used: set[str] = set()

    def reserve(self, decision_id: str) -> bool:
        if decision_id in self._used:
            return False
        self._used.add(decision_id)
        return True


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _route_hash(intent: Mapping[str, Any], rows: list[dict[str, str]]) -> str:
    # Domain-separated digest: a route hash is not a signed attestation.
    envelope = {
        "domain": "VSR-FOR-001-R0.5-STAGING",
        "intent": {key: intent[key] for key in REQUIRED_TEXT},
        "capability": ALLOWED_CAPABILITY,
        "steps": rows,
    }
    encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()


class StagingNavigationChain:
    """Reviewable contracts only; missing ports always HOLD.

    Even if all injected fixtures claim success, no real authority is possible.
    """
    def __init__(self, registrar: RegistrarPort | None = None,
                 identity: IdentityPort | None = None,
                 warden: WardenPort | None = None,
                 river: RiverPort | None = None,
                 replay: ReplayPort | None = None) -> None:
        self.registrar = registrar
        self.identity = identity
        self.warden = warden
        self.river = river
        self.replay = replay

    def evaluate(self, intent: Mapping[str, Any], now: datetime) -> StageOutcome:
        def finish(kind: str, reason: str, digest: str | None = None, ack: bool = False) -> StageOutcome:
            return StageOutcome(kind, reason, digest, ack)

        if not isinstance(intent, Mapping):
            return finish("DENY", "INVALID_INTENT")
        if intent.get("capability") != ALLOWED_CAPABILITY:
            return finish("DENY", "UNSUPPORTED_CAPABILITY")
        if intent.get("execute") is not False or intent.get("mutation") is not False:
            return finish("DENY", "EXECUTION_OR_MUTATION_NOT_ALLOWED")
        if any(not _nonempty(intent.get(field)) for field in REQUIRED_TEXT):
            return finish("HOLD", "MISSING_IDENTITY_SCOPE_OR_PURPOSE")
        steps = intent.get("steps")
        if not isinstance(steps, (tuple, list)) or not 1 <= len(steps) <= 24:
            return finish("DENY", "INVALID_ROUTE_STEPS")
        if any(not _nonempty(s) for s in steps) or len(set(steps)) != len(steps):
            return finish("DENY", "INVALID_OR_DUPLICATE_FRAMEWORK")
        if now.utcoffset() is None:
            return finish("HOLD", "UNTRUSTED_CLOCK")
        now = now.astimezone(timezone.utc)
        expires = _time(intent.get("expires_at"))
        if expires is None or expires <= now:
            return finish("DENY", "INVALID_INTENT_EXPIRY")
        if (expires - now).total_seconds() > 300:
            return finish("DENY", "INTENT_TTL_EXCEEDS_POLICY")
        if any(port is None for port in (self.registrar, self.identity, self.warden, self.river, self.replay)):
            return finish("HOLD", "TRUSTED_SERVICE_ADAPTERS_NOT_CONNECTED")

        try:
            registrations = self.registrar.resolve(tuple(steps), intent["station_id"])
        except Exception:
            return finish("HOLD", "REGISTRAR_PORT_UNAVAILABLE")
        if not isinstance(registrations, Mapping):
            return finish("HOLD", "INVALID_REGISTRAR_RESPONSE")
        rows = []
        genesis_ids = set()
        for source_id in steps:
            record = registrations.get(source_id)
            if not isinstance(record, Mapping) or record.get("registration_state") != "ACTIVE" or record.get("revoked") is not False:
                return finish("HOLD", "REGISTRY_RECORD_NOT_ACTIVE_OR_REVOKED")
            station_ids = record.get("station_ids")
            if not isinstance(station_ids, (list, tuple)) or not all(isinstance(s, str) for s in station_ids):
                return finish("HOLD", "INVALID_REGISTRY_STATION_BINDINGS")
            if intent["station_id"] not in station_ids:
                return finish("DENY", "FRAMEWORK_OUT_OF_STATION_SCOPE")
            required = ("genesis_id", "version", "source_ref", "attestation_ref")
            if any(not _nonempty(record.get(key)) for key in required):
                return finish("HOLD", "REGISTRY_PROVENANCE_INCOMPLETE")
            if record.get("engine_execution_allowed") is not False:
                return finish("DENY", "ENGINE_EXECUTION_REGISTRY_SCOPE")
            if record["genesis_id"] in genesis_ids:
                return finish("HOLD", "GENESIS_ID_COLLISION")
            genesis_ids.add(record["genesis_id"])
            rows.append({"source_id": source_id, **{k: record[k] for k in required}})
        route_digest = _route_hash(intent, rows)

        try:
            principal = self.identity.verify({key: intent[key] for key in REQUIRED_TEXT})
        except Exception:
            return finish("HOLD", "IDENTITY_PORT_UNAVAILABLE", route_digest)
        if not isinstance(principal, Mapping):
            return finish("HOLD", "INVALID_IDENTITY_ASSERTION", route_digest)
        if principal.get("verified") is not True or principal.get("revoked") is not False:
            return finish("HOLD", "IDENTITY_NOT_VERIFIED", route_digest)
        if principal.get("consent_granted") is not True or principal.get("mandate_active") is not True:
            return finish("DENY", "CONSENT_OR_MANDATE_MISSING", route_digest)
        if any(principal.get(key) != intent[key] for key in REQUIRED_TEXT if key != "request_id"):
            return finish("DENY", "IDENTITY_SCOPE_MISMATCH", route_digest)
        if principal.get("capability") != ALLOWED_CAPABILITY or not _nonempty(principal.get("issuer")):
            return finish("HOLD", "IDENTITY_ATTESTATION_INCOMPLETE", route_digest)
        id_expiry = _time(principal.get("expires_at"))
        if id_expiry is None or id_expiry <= now:
            return finish("DENY", "IDENTITY_ATTESTATION_EXPIRED", route_digest)

        payload = {key: intent[key] for key in REQUIRED_TEXT}
        payload.update({"capability": ALLOWED_CAPABILITY, "route_digest": route_digest,
                        "registered_steps": tuple(rows), "intent_expires_at": intent["expires_at"]})
        try:
            decision = self.warden.evaluate(payload)
        except Exception:
            return finish("HOLD", "WARDEN_PORT_UNAVAILABLE", route_digest)
        if not isinstance(decision, Mapping) or decision.get("decision") != "PERMIT":
            return finish("HOLD", "WARDEN_NO_SCOPED_PERMIT", route_digest)
        required_decision = {**{k: intent[k] for k in REQUIRED_TEXT if k != "request_id"},
                             "capability": ALLOWED_CAPABILITY, "route_digest": route_digest,
                             "audience": "vsr.knowledge-roads.staging"}
        if any(decision.get(k) != v for k, v in required_decision.items()):
            return finish("DENY", "WARDEN_SCOPE_OR_ROUTE_MISMATCH", route_digest)
        if any(not _nonempty(decision.get(k)) for k in ("decision_id", "policy_id", "issuer")):
            return finish("HOLD", "WARDEN_ATTESTATION_INCOMPLETE", route_digest)
        if decision.get("revoked") is not False:
            return finish("HOLD", "WARDEN_DECISION_REVOKED", route_digest)
        d_expiry = _time(decision.get("expires_at"))
        if d_expiry is None or not now < d_expiry <= expires or (d_expiry - now).total_seconds() > 120:
            return finish("DENY", "WARDEN_DECISION_EXPIRED_OR_EXCESSIVE", route_digest)

        # A durable replay store and signed decision verification must replace these
        # staging fixtures before any production service is allowed to consume them.
        try:
            reserved = self.replay.reserve(decision["decision_id"])
        except Exception:
            return finish("HOLD", "REPLAY_PORT_UNAVAILABLE", route_digest)
        if reserved is not True:
            return finish("DENY", "DUPLICATE_WARDEN_DECISION", route_digest)

        event = {"event_type": "VSR_NAVIGATION_SIMULATION", "classification": "TEST_ONLY",
                 "route_digest": route_digest, "request_id": intent["request_id"],
                 "decision_id": decision["decision_id"], "action": ALLOWED_CAPABILITY,
                 "result": "STAGING_PREVIEW_ONLY"}
        try:
            receipt = self.river.acknowledge(event)
        except Exception:
            return finish("HOLD", "RIVER_PORT_UNAVAILABLE", route_digest)
        if (not isinstance(receipt, Mapping) or receipt.get("status") != "FIXTURE_ACK"
                or receipt.get("classification") != "TEST_ONLY"
                or receipt.get("route_digest") != route_digest
                or receipt.get("decision_id") != decision["decision_id"]
                or not _nonempty(receipt.get("fixture_receipt_id"))):
            return finish("HOLD", "RIVER_FIXTURE_ACK_MISSING_OR_MISMATCHED", route_digest)
        return finish("STAGING_PREVIEW_ACCEPTED", "NO_LIVE_AUTHORITY_OR_EVIDENCE", route_digest, True)
