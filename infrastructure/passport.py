"""Synthetic-only Genesis DPI node passport checks.

NOT a legal registry, physical inspector, Warden authorization service, sensor
reader or authority issuance endpoint. No side effects.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ID = re.compile(r"^[A-Z][A-Z0-9-]{2,95}$")
_ALLOWED = {"proposed", "registered", "field-review", "accepted", "active", "suspended", "retired"}
_MODES = {"ARK", "ARC", "DIGITAL"}
_KEYS = {
    "schema", "node_id", "mode", "status", "actor_id", "custodian_id",
    "location_ref", "physical_assets", "digital_services",
    "authority_evidence_ids", "physical_acceptance_id",
    "digital_acceptance_id", "warden_policy_id", "river_receipt_ids",
    "execution_enabled", "synthetic_only",
}


class PassportError(ValueError):
    pass


def validate_passport(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise PassportError("INVALID_PASSPORT_SCHEMA")
    if value["schema"] != "genesis.dpi.node-passport.r0.1":
        raise PassportError("UNSUPPORTED_PASSPORT_VERSION")
    if value["mode"] not in _MODES or value["status"] not in _ALLOWED:
        raise PassportError("INVALID_NODE_MODE_OR_STATE")
    if not all(isinstance(value[k], str) and _ID.fullmatch(value[k]) for k in ("node_id", "actor_id", "custodian_id")):
        raise PassportError("INVALID_ACTOR_OR_NODE_ID")
    if not isinstance(value["synthetic_only"], bool) or value["synthetic_only"] is not True:
        raise PassportError("SYNTHETIC_ONLY_RELEASE")
    if type(value["execution_enabled"]) is not bool or value["execution_enabled"]:
        raise PassportError("REMOTE_EXECUTION_NOT_AUTHORIZED")
    for k in ("physical_assets", "digital_services", "authority_evidence_ids", "river_receipt_ids"):
        entries = value[k]
        if not isinstance(entries, list) or len(entries) > 100 or not all(isinstance(x, str) and _ID.fullmatch(x) for x in entries):
            raise PassportError("INVALID_REFERENCE_COLLECTION")
        if len(set(entries)) != len(entries):
            raise PassportError("DUPLICATE_REFERENCE")
    for k in ("location_ref", "physical_acceptance_id", "digital_acceptance_id", "warden_policy_id"):
        entry = value[k]
        if entry is not None and (not isinstance(entry, str) or not _ID.fullmatch(entry)):
            raise PassportError("INVALID_OPTIONAL_REFERENCE")

    mode = value["mode"]
    has_physical = bool(value["location_ref"] and value["physical_assets"])
    has_digital = bool(value["digital_services"])
    if mode in ("ARK", "ARC") and not has_physical:
        raise PassportError("PHYSICAL_SITE_AND_ASSET_REQUIRED")
    if mode == "DIGITAL" and (value["location_ref"] is not None or value["physical_assets"]):
        raise PassportError("DIGITAL_ONLY_CANNOT_CLAIM_SITE")
    if mode == "ARK" and any(x.startswith(("TAKEOVER-", "TRANSFER-OWNERSHIP-")) for x in value["authority_evidence_ids"]):
        raise PassportError("ARK_DOES_NOT_TRANSFER_CONTROL")
    if mode == "ARC" and not value["authority_evidence_ids"]:
        raise PassportError("ARC_REQUIRES_LEGAL_AUTHORITY_EVIDENCE")
    if mode == "ARC" and not any(x.startswith("ARC-AUTH-") for x in value["authority_evidence_ids"]):
        raise PassportError("ARC_REQUIRES_SPECIFIC_INTERVENTION_AUTHORITY")
    if value["status"] in ("accepted", "active"):
        if not value["warden_policy_id"] or not value["authority_evidence_ids"]:
            raise PassportError("AUTHORITY_AND_WARDEN_REQUIRED")
        if mode != "DIGITAL" and not value["physical_acceptance_id"]:
            raise PassportError("PHYSICAL_ACCEPTANCE_REQUIRED")
        if has_digital and not value["digital_acceptance_id"]:
            raise PassportError("DIGITAL_ACCEPTANCE_REQUIRED")
        if not value["river_receipt_ids"]:
            raise PassportError("EVIDENCE_REQUIRED")
    # This validator CANNOT promote anyone to an operating state.
    return {"node_id": value["node_id"], "mode": mode, "status": value["status"],
            "physical_bound": has_physical, "digital_bound": has_digital,
            "execution_enabled": False, "verification": "synthetic-schema-only",
            "physically_commissioned": False, "independently_witnessed": False}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 -m infrastructure.passport manifest.json")
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(validate_passport(payload), sort_keys=True))


if __name__ == "__main__":
    main()
