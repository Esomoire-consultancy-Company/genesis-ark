"""Deterministic, synthetic-only authorization oracle for CI.

No transport, network, persistence, live identity or external side effects.
These outcomes are fixture expectations, NOT live Warden decisions.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED_REQUEST_FIELDS = frozenset({
    "request_id", "actor_id", "action", "environment", "node_id", "legal_supplier_id"
})


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def when(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return parsed.astimezone(timezone.utc)


def load_manifest(path: Path | None = None) -> dict:
    location = path or (ROOT / "fixtures.json")
    manifest = json.loads(location.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def validate_manifest(m: dict) -> None:
    if not isinstance(m, dict) or m.get("schema_version") != "0.1":
        raise ValueError("wrong synthetic fixture schema")
    if m.get("synthetic") is not True or m.get("environment") != "synthetic-ci":
        raise ValueError("fixture must be synthetic and isolated")
    if m.get("fixture_id") != "GENESIS-SYNTHETIC-BASELINE-R01":
        raise ValueError("unrecognised fixture identity")
    when(m["test_clock"])
    for collection, key in (("organizations", "id"), ("actors", "id"),
                            ("licences", "id"), ("action_policies", "action"),
                            ("representations", "id")):
        items = m.get(collection)
        if not isinstance(items, list) or not items:
            raise ValueError(f"missing {collection}")
        identifiers = [item[key] for item in items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"duplicate {collection} identity")
    actors = {item["id"] for item in m["actors"]}
    organizations = {item["id"] for item in m["organizations"]}
    actions = {item["action"] for item in m["action_policies"]}
    if any(not value.startswith("SYN-") for value in actors | organizations):
        raise ValueError("live-looking actor or organization ID")
    if any(not a.endswith(".synthetic") for a in actions):
        raise ValueError("non-synthetic capability")
    if any(a["state"] not in ("ACTIVE", "DISABLED") for a in m["actors"]):
        raise ValueError("unsupported actor state")
    for membership in m["memberships"]:
        if membership["actor_id"] not in actors:
            raise ValueError("membership points at unknown actor")
        if membership["commons_id"] not in organizations:
            raise ValueError("membership points at unknown commons")
    for representation in m["representations"]:
        if representation["actor_id"] not in actors or representation["node_id"] not in organizations:
            raise ValueError("representation points at unknown principal or node")
        when(representation["valid_until"])
    for licence in m["licences"]:
        if licence.get("synthetic") is not True or not licence["id"].startswith("SYN-LIC-"):
            raise ValueError("licence is not explicitly synthetic")
        if licence["actor_id"] not in actors:
            raise ValueError("licence points at unknown actor")
        if not licence["actions"] or any(action not in actions for action in licence["actions"]):
            raise ValueError("licence includes unknown capability")
        if "node_id" in licence and licence["node_id"] not in organizations:
            raise ValueError("licence points at unknown node")
        if "legal_supplier_id" in licence and licence["legal_supplier_id"] not in organizations:
            raise ValueError("licence points at unknown supplier")
        when(licence["valid_until"])
    for policy in m["action_policies"]:
        if not isinstance(policy.get("review_required"), bool):
            raise ValueError("policy missing explicit review semantics")
        if not isinstance(policy.get("requires_representation"), bool):
            raise ValueError("policy missing representation semantics")
    # Avoid accidentally bundling credentials or real identity data in fixtures.
    forbidden_keys = {"password", "token", "api_key", "secret", "email", "phone", "private_key"}
    def walk(item):
        if isinstance(item, dict):
            if forbidden_keys.intersection(item):
                raise ValueError("credential or personal data in fixture")
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)
    walk(m)


class SyntheticOracle:
    """Expected permission outcomes only. Never executes a requested action."""

    def __init__(self, manifest: dict):
        validate_manifest(manifest)
        self.manifest = manifest
        self._seen: dict[str, tuple[str, dict]] = {}
        self.effects = 0  # must stay at zero, including ALLOW and ESCALATE

    def evaluate(self, request: dict) -> dict:
        if not isinstance(request, dict):
            raise ValueError("request must be a dictionary")
        # Reject attempts to supply decisions, authority or arbitrary fields.
        invalid_fields = set(request) - ALLOWED_REQUEST_FIELDS
        if invalid_fields:
            raise ValueError("unexpected request fields")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id.startswith("SYN-REQ-"):
            raise ValueError("request must have a synthetic request ID")
        fingerprint = digest(request)
        if request_id in self._seen:
            previous_digest, previous_receipt = self._seen[request_id]
            if previous_digest != fingerprint:
                raise ValueError("request replay conflict")
            return dict(previous_receipt)
        decision, reason = self._decide(request)
        receipt = {
            "fixture_id": self.manifest["fixture_id"],
            "request_id": request_id,
            "synthetic": True,
            "executable": False,
            "decision": decision,
            "reason_code": reason,
            "actor_id": request.get("actor_id"),
            "action": request.get("action"),
            "test_clock": self.manifest["test_clock"],
            "request_sha256": fingerprint,
        }
        receipt["evidence_sha256"] = digest(receipt)
        self._seen[request_id] = (fingerprint, dict(receipt))
        return receipt

    def _decide(self, r: dict) -> tuple[str, str]:
        if r.get("environment") != "synthetic-ci":
            return "DENY", "ENVIRONMENT_DENIED"
        if not isinstance(r.get("action"), str) or not r["action"].endswith(".synthetic"):
            return "DENY", "UNKNOWN_ACTION"
        policy = next((x for x in self.manifest["action_policies"] if x["action"] == r["action"]), None)
        if policy is None:
            return "DENY", "UNKNOWN_ACTION"
        actor = next((x for x in self.manifest["actors"] if x["id"] == r.get("actor_id")), None)
        if actor is None:
            return "DENY", "UNKNOWN_ACTOR"
        if actor["state"] != "ACTIVE":
            return "DENY", "IDENTITY_INACTIVE"
        membership = next((x for x in self.manifest["memberships"] if x["actor_id"] == actor["id"]), None)
        if membership is None:
            return "DENY", "COMMONS_MEMBERSHIP_REQUIRED"
        if membership["state"] != "ACTIVE":
            return "DENY", "COMMONS_MEMBERSHIP_INACTIVE"
        if actor["role"] != policy["role"]:
            return "DENY", "ROLE_DENIED"
        if policy["requires_representation"]:
            node = r.get("node_id")
            if not node:
                return "DENY", "NODE_SCOPE_REQUIRED"
            reps = [x for x in self.manifest["representations"] if x["actor_id"] == actor["id"]]
            if not any(x["node_id"] == node and x["state"] == "ACTIVE"
                       and when(x["valid_until"]) > when(self.manifest["test_clock"]) for x in reps):
                return "DENY", "NODE_REPRESENTATION_DENIED"
            supplier = r.get("legal_supplier_id")
            if not supplier:
                return "DENY", "LEGAL_SUPPLIER_REQUIRED"
            suppliers = [x for x in self.manifest["organizations"]
                         if x["id"] == supplier and x["kind"] == "legal_supplier"]
            if not suppliers:
                return "DENY", "LEGAL_SUPPLIER_DENIED"
        licenses = [lic for lic in self.manifest["licences"] if lic["actor_id"] == actor["id"]
                    and r["action"] in lic["actions"]]
        if not licenses:
            return "DENY", "SYNTHETIC_LICENCE_MISSING"
        clock = when(self.manifest["test_clock"])
        if not any(lic["state"] == "ACTIVE" and when(lic["valid_until"]) > clock for lic in licenses):
            return "DENY", "SYNTHETIC_LICENCE_EXPIRED_OR_INACTIVE"
        if policy["requires_representation"] and not any(
            lic.get("node_id") == r["node_id"] and
            lic.get("legal_supplier_id") == r["legal_supplier_id"] and
            lic["state"] == "ACTIVE" and when(lic["valid_until"]) > clock
            for lic in licenses
        ):
            return "DENY", "LICENCE_SCOPE_MISMATCH"
        if policy["review_required"]:
            return "ESCALATE", "SYNTHETIC_REVIEW_REQUIRED"
        return "ALLOW", "SYNTHETIC_POLICY_ALLOW"
