#!/usr/bin/env python3
"""Offline validation for the Actor Box foundation contracts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/actor-box/v1/actor-box.schema.json"
OPENAPI_PATH = ROOT / "openapi/warden/v1/openapi.yaml"
EXAMPLES_DIR = ROOT / "examples/actor-box/v1"
DDL_PATH = ROOT / "db/actor-box/v1/001_actor_box_foundation.sql"

REQUIRED_TABLES = {
    "actor_boxes",
    "actor_box_bindings",
    "box_runtimes",
    "box_contexts",
    "warden_policy_profiles",
    "consent_receipts",
    "delegated_agents",
    "warden_policy_decisions",
    "capability_grants",
    "data_boundary_rules",
    "box_evidence_events",
    "box_revocations",
    "box_recovery_authorities",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_schema_and_examples() -> None:
    schema = load_json(SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )

    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        instance = load_json(path)
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        if errors:
            details = "\n".join(f"{path.name}: {error.message}" for error in errors)
            raise AssertionError(details)

    decision = load_json(EXAMPLES_DIR / "policy-decision.json")
    capability = decision["capability"]
    if parse_time(capability["expires_at"]) <= parse_time(capability["issued_at"]):
        raise AssertionError("Capability expiry must be later than issuance")


def validate_openapi() -> None:
    with OPENAPI_PATH.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if document.get("openapi") != "3.1.0":
        raise AssertionError("OpenAPI version must be 3.1.0")

    paths = document.get("paths", {})
    if not paths:
        raise AssertionError("OpenAPI document must define paths")

    operation_ids: set[str] = set()
    for path_name, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                raise AssertionError(f"Missing operationId for {method.upper()} {path_name}")
            if operation_id in operation_ids:
                raise AssertionError(f"Duplicate operationId: {operation_id}")
            operation_ids.add(operation_id)
            if "security" not in operation:
                raise AssertionError(f"Missing operation security for {method.upper()} {path_name}")

    evaluate = paths["/v1/policy-decisions/evaluate"]["post"]
    if "default outcome is DENY" not in evaluate.get("description", ""):
        raise AssertionError("Policy evaluation contract must state deny-by-default behavior")


def validate_ddl() -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8").lower()
    missing = sorted(table for table in REQUIRED_TABLES if f"create table {table}" not in ddl)
    if missing:
        raise AssertionError(f"DDL is missing canonical tables: {', '.join(missing)}")
    if "create view active_capability_grants" not in ddl:
        raise AssertionError("DDL must provide the deny-by-default active capability view")


def main() -> int:
    validate_schema_and_examples()
    validate_openapi()
    validate_ddl()
    print("Actor Box foundation contracts validated successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should report all validation failures.
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
