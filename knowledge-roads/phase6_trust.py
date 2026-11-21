"""VSR-FOR-001 R0.6: cryptographically checked staging fixtures, never live authority.

Production admission is intentionally not implemented. Caller-supplied signed
fixtures are checked against explicitly pinned *staging* trust roots. No root
keys are provided by this module. No engine, registrar, Warden or River service
is contacted, and no authentic RiverOS receipt is emitted.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

DOMAIN = b"VSR-FOR-001-R06-STAGING\0"
AUDIENCE = "vsr.knowledge-roads.staging"
CAPABILITY = "navigate.readonly"
SCOPED = ("principal_id", "session_id", "estate_id", "station_id", "location_id", "purpose")
KINDS = ("GENESIS_SNAPSHOT", "DIGITALME_ASSERTION", "WARDEN_NAV_DECISION", "RIVER_TEST_ACK")


def canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def fingerprint(value: Mapping[str, Any]) -> str:
    return sha256(canonical(value)).hexdigest()


def utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class StageDecision:
    disposition: str
    reason: str
    route_digest: str | None = None
    simulated_ack_recorded: bool = False
    authority_granted: bool = False
    engine_execution_allowed: bool = False
    real_river_receipt_emitted: bool = False


class StagingTrust:
    """Explicit, pinned keys: (kind, key_id) -> (issuer, Ed25519PublicKey).

    Caller must provision approved test public keys. In particular, arbitrary
    envelope-supplied keys and issuer labels are NEVER trusted.
    """
    def __init__(self, roots: Mapping[tuple[str, str], tuple[str, Ed25519PublicKey]]):
        self._roots = dict(roots)

    def verify(self, envelope: Any, kind: str) -> dict[str, Any] | None:
        if kind not in KINDS or not isinstance(envelope, Mapping):
            return None
        if envelope.get("kind") != kind or envelope.get("alg") != "Ed25519":
            return None
        kid, payload = envelope.get("kid"), envelope.get("payload")
        if not nonempty(kid) or not isinstance(payload, dict):
            return None
        anchor = self._roots.get((kind, kid))
        if not anchor or payload.get("issuer") != anchor[0]:
            return None
        signature = envelope.get("signature")
        if not isinstance(signature, str):
            return None
        try:
            sig = base64.b64decode(signature, altchars=b"-_", validate=True)
            if len(sig) != 64:
                return None
            signed = {"kind": kind, "alg": "Ed25519", "kid": kid, "payload": payload}
            anchor[1].verify(sig, DOMAIN + canonical(signed))
            return payload
        except (InvalidSignature, ValueError, TypeError, OverflowError):
            return None


class DurableReplay:
    """File-backed SQLite uniqueness gate; fixture receipts only. No distributed HA."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Persistent database path required for replay durability")
        with closing(self._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS staging_navigation (
                issuer TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                route_digest TEXT NOT NULL,
                request_id TEXT NOT NULL,
                fixture_receipt_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(issuer, decision_id)
            )""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    def commit_fixture(self, issuer: str, decision_id: str, nonce: str, route_digest: str,
                       request_id: str, receipt_id: str, now: datetime) -> bool:
        with closing(self._connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""INSERT INTO staging_navigation
                  (issuer,decision_id,nonce,route_digest,request_id,fixture_receipt_id,created_at)
                  VALUES (?,?,?,?,?,?,?)""",
                           (issuer, decision_id, nonce, route_digest, request_id,
                            receipt_id, now.isoformat()))
                db.execute("COMMIT")
                return True
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK")
                return False


class VerifiedStagingNavigator:
    """Validates four signed staging fixtures and atomically records simulated ack.

    Never returns an operational Warden PERMIT; does not connect to any service.
    """
    def __init__(self, trust: StagingTrust, replay: DurableReplay):
        self.trust = trust
        self.replay = replay

    def evaluate(self, intent: Mapping[str, Any], signatures: Mapping[str, Any],
                 now: datetime) -> StageDecision:
        def result(state: str, reason: str, digest: str | None = None,
                   ack: bool = False) -> StageDecision:
            return StageDecision(state, reason, digest, ack)

        if not isinstance(intent, Mapping) or not isinstance(signatures, Mapping):
            return result("DENY", "MALFORMED_INPUT")
        if intent.get("capability") != CAPABILITY or intent.get("execute") is not False or intent.get("mutation") is not False:
            return result("DENY", "READONLY_CAPABILITY_ONLY")
        if not nonempty(intent.get("request_id")) or any(not nonempty(intent.get(k)) for k in SCOPED):
            return result("HOLD", "INTENT_SCOPE_INCOMPLETE")
        steps = intent.get("steps")
        if not isinstance(steps, (tuple, list)) or not 1 <= len(steps) <= 24 or any(not nonempty(x) for x in steps):
            return result("DENY", "INVALID_STEPS")
        if len(set(steps)) != len(steps):
            return result("DENY", "DUPLICATE_STEPS")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            return result("HOLD", "UNTRUSTED_CLOCK")
        now = now.astimezone(timezone.utc)
        requested_expiry = utc(intent.get("expires_at"))
        if requested_expiry is None or requested_expiry <= now:
            return result("DENY", "INTENT_TIME_INVALID")
        if (requested_expiry - now).total_seconds() > 300:
            return result("DENY", "INTENT_TTL_EXCESSIVE")

        for key, kind in (("genesis", KINDS[0]), ("digitalme", KINDS[1]),
                          ("warden", KINDS[2]), ("river", KINDS[3])):
            if key not in signatures:
                return result("HOLD", "SIGNED_FIXTURE_MISSING")
        registry = self.trust.verify(signatures["genesis"], KINDS[0])
        if registry is None:
            return result("DENY", "REGISTRY_SIGNATURE_UNTRUSTED")
        if registry.get("audience") != AUDIENCE or registry.get("station_id") != intent["station_id"]:
            return result("DENY", "REGISTRY_SCOPE_MISMATCH")
        if registry.get("revoked") is not False or not nonempty(registry.get("snapshot_id")):
            return result("HOLD", "REGISTRY_SNAPSHOT_NOT_VALID")
        if not self._fresh(registry, now):
            return result("DENY", "REGISTRY_SNAPSHOT_EXPIRED")
        objects = registry.get("objects")
        if not isinstance(objects, Mapping):
            return result("HOLD", "REGISTRY_OBJECTS_MISSING")
        bound = []
        seen_ids = set()
        for sid in steps:
            item = objects.get(sid)
            if not isinstance(item, Mapping) or item.get("state") != "ACTIVE" or item.get("revoked") is not False:
                return result("HOLD", "FRAMEWORK_NOT_ACTIVE")
            fields = ("genesis_id", "version", "source_ref", "attestation_ref")
            if any(not nonempty(item.get(k)) for k in fields):
                return result("HOLD", "FRAMEWORK_PROVENANCE_INCOMPLETE")
            stations = item.get("station_ids")
            if not isinstance(stations, list) or intent["station_id"] not in stations:
                return result("DENY", "FRAMEWORK_STATION_DENIED")
            if item.get("engine_execution_allowed") is not False:
                return result("DENY", "FRAMEWORK_ENGINE_SCOPE_DENIED")
            if item["genesis_id"] in seen_ids:
                return result("DENY", "FRAMEWORK_ID_COLLISION")
            seen_ids.add(item["genesis_id"])
            bound.append({"framework": sid, **{k: item[k] for k in fields}})
        route_digest = fingerprint({"domain": "VSR-FOR-001-R06-ROUTE",
                                    "scope": {k: intent[k] for k in SCOPED},
                                    "request_id": intent["request_id"],
                                    "capability": CAPABILITY, "snapshot_id": registry["snapshot_id"],
                                    "frameworks": bound})

        identity = self.trust.verify(signatures["digitalme"], KINDS[1])
        if identity is None:
            return result("DENY", "IDENTITY_SIGNATURE_UNTRUSTED", route_digest)
        if any(identity.get(k) != intent[k] for k in SCOPED) or identity.get("audience") != AUDIENCE:
            return result("DENY", "IDENTITY_SCOPE_MISMATCH", route_digest)
        if identity.get("verified") is not True or identity.get("revoked") is not False:
            return result("HOLD", "IDENTITY_NOT_VERIFIED", route_digest)
        if identity.get("consent") is not True or identity.get("mandate") is not True:
            return result("DENY", "CONSENT_OR_MANDATE_DENIED", route_digest)
        if identity.get("capability") != CAPABILITY or not self._fresh(identity, now):
            return result("DENY", "IDENTITY_ASSERTION_INVALID", route_digest)
        assertion_digest = fingerprint(identity)

        decision = self.trust.verify(signatures["warden"], KINDS[2])
        if decision is None:
            return result("DENY", "WARDEN_SIGNATURE_UNTRUSTED", route_digest)
        if decision.get("audience") != AUDIENCE or any(decision.get(k) != intent[k] for k in SCOPED):
            return result("DENY", "WARDEN_SCOPE_MISMATCH", route_digest)
        if (decision.get("decision") != "PERMIT" or decision.get("capability") != CAPABILITY
                or decision.get("route_digest") != route_digest
                or decision.get("identity_digest") != assertion_digest):
            return result("DENY", "WARDEN_DECISION_MISMATCH", route_digest)
        if decision.get("revoked") is not False or not all(nonempty(decision.get(k)) for k in ("decision_id", "nonce", "policy_id", "policy_version")):
            return result("HOLD", "WARDEN_DECISION_INCOMPLETE", route_digest)
        if len(decision["nonce"]) < 16 or not self._fresh(decision, now, 120):
            return result("DENY", "WARDEN_DECISION_EXPIRED", route_digest)
        if utc(decision.get("expires_at")) > requested_expiry:
            return result("DENY", "WARDEN_OUTLIVES_INTENT", route_digest)

        receipt = self.trust.verify(signatures["river"], KINDS[3])
        if receipt is None:
            return result("HOLD", "RIVER_FIXTURE_SIGNATURE_UNTRUSTED", route_digest)
        if (receipt.get("audience") != AUDIENCE or receipt.get("classification") != "TEST_ONLY"
                or receipt.get("status") != "SIMULATED_ACK"
                or receipt.get("route_digest") != route_digest
                or receipt.get("decision_id") != decision["decision_id"]
                or not nonempty(receipt.get("fixture_receipt_id"))
                or not self._fresh(receipt, now, 120)):
            return result("HOLD", "RIVER_FIXTURE_NOT_MATCHED", route_digest)
        try:
            fresh = self.replay.commit_fixture(decision["issuer"], decision["decision_id"],
                                               decision["nonce"], route_digest, intent["request_id"],
                                               receipt["fixture_receipt_id"], now)
        except (sqlite3.Error, OSError):
            return result("HOLD", "DURABLE_REPLAY_UNAVAILABLE", route_digest)
        if not fresh:
            return result("DENY", "REPLAY_DETECTED", route_digest)
        return result("STAGING_CRYPTO_VERIFIED_ONLY", "NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT",
                      route_digest, True)

    @staticmethod
    def _fresh(payload: Mapping[str, Any], now: datetime, maximum_seconds: int = 300) -> bool:
        issued, expiry = utc(payload.get("issued_at")), utc(payload.get("expires_at"))
        return bool(issued is not None and expiry is not None and issued <= now < expiry
                    and 0 < (expiry-issued).total_seconds() <= maximum_seconds)