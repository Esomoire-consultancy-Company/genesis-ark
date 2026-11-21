"""VSR-FOR-001 R0.7: review-only, independently signed STAGING FIXTURE acceptance.

No services are contacted. Signed simulated evidence NEVER grants authorization,
registration, Warden navigation rights, engine execution, or RiverOS receipts.
The only successful disposition is SIMULATED_ACCEPTANCE_COMPLETE.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

DOMAIN = b"VSR-FOR-001-R07-ACCEPTANCE\0"
REQUIRED_ROLES = ("GENESIS_REGISTRAR", "DIGITALME", "WARDEN", "RIVEROS", "REPLAY_LEDGER", "SECURITY", "HUMAN_REVIEW")
AUDIENCE = "vsr.knowledge-roads.staging"
VALID_SHA = re.compile(r"^[0-9a-f]{40}$")
VALID_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def hex_digest(value: Mapping[str, Any]) -> str:
    return sha256(canonical(value)).hexdigest()


def aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


@dataclass(frozen=True)
class AcceptanceResult:
    disposition: str
    reason: str
    plan_digest: str | None = None
    locally_verified_roles: tuple[str, ...] = ()
    real_staging_accepted: bool = False
    live_navigation_authorized: bool = False
    engine_execution_allowed: bool = False
    river_receipt_emitted: bool = False
    merge_or_deploy_allowed: bool = False


class FixtureTrust:
    """Explicit role-separated fixture public keys supplied outside payloads.

    Never populate this with user-input envelope keys. Real trust anchors and
    service attestation must be established by a separate authorized verifier.
    """
    def __init__(self, anchors: Mapping[tuple[str, str], tuple[str, Ed25519PublicKey]]):
        self._anchors: dict[tuple[str, str], tuple[str, Ed25519PublicKey]] = {}
        used = set()
        for (role, kid), (issuer, public_key) in anchors.items():
            if role not in REQUIRED_ROLES or not valid_text(kid) or not valid_text(issuer):
                raise ValueError("Invalid role, key id, or issuer")
            if not isinstance(public_key, Ed25519PublicKey):
                raise TypeError("Ed25519PublicKey required")
            fingerprint = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            # A fixture signer cannot impersonate multiple independent checks.
            if fingerprint in used:
                raise ValueError("Each acceptance role requires an independent key")
            used.add(fingerprint)
            self._anchors[(role, kid)] = (issuer, public_key)

    def verify(self, role: str, candidate: Any) -> Mapping[str, Any] | None:
        if role not in REQUIRED_ROLES or not isinstance(candidate, Mapping):
            return None
        if candidate.get("role") != role or candidate.get("alg") != "Ed25519":
            return None
        kid, payload, signature = candidate.get("kid"), candidate.get("payload"), candidate.get("signature")
        if not valid_text(kid) or not isinstance(payload, dict) or not isinstance(signature, str):
            return None
        anchor = self._anchors.get((role, kid))
        if anchor is None or payload.get("issuer") != anchor[0]:
            return None
        try:
            raw = base64.b64decode(signature, altchars=b"-_", validate=True)
            if len(raw) != 64:
                return None
            data = {"role": role, "kid": kid, "alg": "Ed25519", "payload": payload}
            anchor[1].verify(raw, DOMAIN + canonical(data))
        except (InvalidSignature, ValueError, TypeError, OverflowError):
            return None
        return payload


class Phase7AcceptanceGate:
    """Validate seven separately signed fixture assertions against a fixed plan.

    No network access or production promotion path exists in this class.
    """
    def __init__(self, trust: FixtureTrust):
        self.trust = trust

    def evaluate(self, plan: Mapping[str, Any], envelopes: Mapping[str, Any],
                 now: datetime) -> AcceptanceResult:
        def output(disposition: str, reason: str, dig: str | None = None,
                   roles: tuple[str, ...] = ()) -> AcceptanceResult:
            return AcceptanceResult(disposition, reason, dig, roles)

        if not isinstance(plan, Mapping) or not isinstance(envelopes, Mapping):
            return output("DENY", "MALFORMED_INPUT")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            return output("HOLD", "TRUSTED_CLOCK_NOT_SUPPLIED")
        now = now.astimezone(timezone.utc)
        if plan.get("environment") != "staging" or plan.get("action") != "navigate.readonly":
            return output("DENY", "ENVIRONMENT_OR_CAPABILITY_INVALID")
        if plan.get("execute") is not False or plan.get("mutation") is not False:
            return output("DENY", "EXECUTION_FORBIDDEN")
        if plan.get("promotion_requested") is not False:
            return output("DENY", "PROMOTION_NOT_ALLOWED")
        required = ("pilot_id", "run_id", "station_id", "estate_id", "purpose")
        if any(not valid_text(plan.get(key)) for key in required):
            return output("HOLD", "INCOMPLETE_ACCEPTANCE_SCOPE")
        if not isinstance(plan.get("commit_sha"), str) or not VALID_SHA.fullmatch(plan["commit_sha"]):
            return output("HOLD", "UNBOUND_GIT_COMMIT")
        if not isinstance(plan.get("route_digest"), str) or not VALID_DIGEST.fullmatch(plan["route_digest"]):
            return output("HOLD", "INVALID_ROUTE_DIGEST")
        allowed_fields = {"environment", "action", "execute", "mutation", "promotion_requested",
                          "pilot_id", "run_id", "station_id", "estate_id", "purpose",
                          "commit_sha", "route_digest", "source_registry_status"}
        if set(plan) != allowed_fields:
            return output("DENY", "UNSUPPORTED_PLAN_FIELDS")
        if plan.get("source_registry_status") != "UNREGISTERED_PROPOSALS":
            return output("HOLD", "REGISTRATION_STATUS_NOT_PROVEN")
        plan_fields = {key: plan[key] for key in (
            "environment", "action", "execute", "mutation", "promotion_requested",
            "pilot_id", "run_id", "station_id", "estate_id", "purpose",
            "commit_sha", "route_digest", "source_registry_status")}
        plan_digest = hex_digest({"domain": "VSR-FOR-001-R07-PLAN", "plan": plan_fields})

        checked: list[str] = []
        evidence_ids = set()
        issuers = set()
        for role in REQUIRED_ROLES:
            if role not in envelopes:
                return output("HOLD", "REQUIRED_INDEPENDENT_EVIDENCE_MISSING", plan_digest, tuple(checked))
            signed = self.trust.verify(role, envelopes[role])
            if signed is None:
                return output("DENY", "EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", plan_digest, tuple(checked))
            if (signed.get("audience") != AUDIENCE or signed.get("plan_digest") != plan_digest
                    or signed.get("commit_sha") != plan["commit_sha"]
                    or signed.get("route_digest") != plan["route_digest"]
                    or signed.get("environment") != "staging" or signed.get("run_id") != plan["run_id"]
                    or signed.get("pilot_id") != plan["pilot_id"]
                    or signed.get("station_id") != plan["station_id"]
                    or signed.get("estate_id") != plan["estate_id"]
                    or signed.get("purpose") != plan["purpose"]):
                return output("DENY", "EVIDENCE_SCOPE_OR_VERSION_MISMATCH", plan_digest, tuple(checked))
            if signed.get("classification") != "TEST_ONLY" or signed.get("is_fixture") is not True:
                return output("HOLD", "REAL_SERVICE_ASSERTION_NOT_VERIFIED", plan_digest, tuple(checked))
            if signed.get("status") != "PASS":
                return output("HOLD", "ACCEPTANCE_GATE_NOT_PASSED", plan_digest, tuple(checked))
            evidence_id, issuer = signed.get("evidence_id"), signed.get("issuer")
            if not valid_text(evidence_id) or not valid_text(issuer):
                return output("HOLD", "MISSING_EVIDENCE_PROVENANCE", plan_digest, tuple(checked))
            if evidence_id in evidence_ids or issuer in issuers:
                return output("DENY", "INDEPENDENCE_OR_EVIDENCE_ID_COLLISION", plan_digest, tuple(checked))
            evidence_ids.add(evidence_id)
            issuers.add(issuer)
            issue, expiry = aware(signed.get("issued_at")), aware(signed.get("expires_at"))
            if (issue is None or expiry is None or issue > now or expiry <= now
                    or not 0 < (expiry - issue).total_seconds() <= 600):
                return output("HOLD", "EVIDENCE_EXPIRED_OR_TIME_UNTRUSTED", plan_digest, tuple(checked))
            checked.append(role)
        return output("SIMULATED_ACCEPTANCE_COMPLETE", "ALL_CHECKS_SYNTHETIC_NO_REAL_STAGING_ACCEPTANCE",
                      plan_digest, tuple(checked))
