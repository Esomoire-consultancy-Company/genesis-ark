#!/usr/bin/env python3
"""Offline validation for governed CloudBrowser contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/cloudbrowser/v1/cloudbrowser.schema.json"
OPENAPI_PATH = ROOT / "openapi/cloudbrowser/v1/openapi.yaml"
EXAMPLES_DIR = ROOT / "examples/cloudbrowser/v1"
DDL_PATH = ROOT / "db/cloudbrowser/v1/002_cloud_browser_foundation.sql"

REQUIRED_TABLES = {
    "cloud_browser_policies",
    "cloud_browser_sessions",
    "cloud_browser_actions",
    "cloud_browser_approvals",
    "cloud_browser_usage",
    "cloud_browser_evidence_events",
}

EXPECTED_OPERATION_IDS = {
    "createGovernedBrowserSession",
    "getGovernedBrowserSession",
    "evaluateGovernedBrowserAction",
    "approveGovernedBrowserAction",
    "pauseGovernedBrowserSession",
    "terminateGovernedBrowserSession",
    "getGovernedBrowserEvidence",
    "getGovernedBrowserUsage",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def validate_openapi() -> None:
    document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    if document.get("openapi") != "3.1.0":
        raise AssertionError("CloudBrowser OpenAPI must use version 3.1.0")
    operation_ids: set[str] = set()
    for path_name, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                raise AssertionError(f"Missing operationId for {method.upper()} {path_name}")
            operation_ids.add(operation_id)
            if operation.get("security") != [{"mutualTLS": [], "bearerAuth": []}]:
                raise AssertionError(f"Incorrect security for {method.upper()} {path_name}")
    if operation_ids != EXPECTED_OPERATION_IDS:
        raise AssertionError(
            f"CloudBrowser operation IDs differ: {sorted(operation_ids)}"
        )


def validate_ddl() -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8").lower()
    missing = sorted(table for table in REQUIRED_TABLES if f"create table {table}" not in ddl)
    if missing:
        raise AssertionError(f"CloudBrowser DDL missing: {', '.join(missing)}")
    if "create view active_cloud_browser_sessions" not in ddl:
        raise AssertionError("Deny-by-default active session view is missing")
    if "references capability_grants" not in ddl:
        raise AssertionError("CloudBrowser sessions must bind Warden capabilities")


def main() -> int:
    validate_schema_and_examples()
    validate_openapi()
    validate_ddl()
    print("CloudBrowser foundation contracts validated successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
