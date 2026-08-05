from __future__ import annotations

from pathlib import Path
import json
import sys

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "db/runtime/v1/004_genesis_runtime_platform.sql"
OPENAPI = ROOT / "openapi/runtime/v1/openapi.yaml"
SCHEMA = ROOT / "schemas/runtime/v1/runtime.schema.json"

EXPECTED_TABLES = {
    "runtime_nodes",
    "runtime_instances",
    "runtime_sessions",
    "runtime_resource_allocations",
    "runtime_health_reports",
    "runtime_recovery_jobs",
    "runtime_events",
}
EXPECTED_OPERATIONS = {
    "registerRuntimeNode",
    "provisionRuntimeInstance",
    "getRuntimeInstance",
    "attestRuntimeInstance",
    "createRuntimeSession",
    "allocateRuntimeResources",
    "reportRuntimeHealth",
    "terminateRuntimeSession",
    "listRuntimeEvents",
}
EXPECTED_DEFINITIONS = {
    "RegisterNodeRequest",
    "RuntimeNode",
    "ProvisionInstanceRequest",
    "RuntimeInstance",
    "AttestInstanceRequest",
    "CreateSessionRequest",
    "RuntimeSession",
    "AllocateResourcesRequest",
    "ResourceAllocation",
    "HealthReportRequest",
    "RuntimeHealthReport",
    "RecoveryJob",
    "TerminateSessionRequest",
    "RuntimeEvent",
    "CapabilityAuthorization",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    sql = SQL.read_text()
    lowered = sql.lower()
    for table in EXPECTED_TABLES:
        if f"create table genesis_runtime.{table}" not in lowered:
            fail(f"missing runtime table: {table}")
        if f"alter table genesis_runtime.{table} enable row level security" not in lowered:
            fail(f"RLS is not enabled for: {table}")
    if "with (security_invoker = true)" not in lowered:
        fail("active runtime view is not security-invoker")
    if "revoke all on schema genesis_runtime from public, anon, authenticated" not in lowered:
        fail("private runtime schema is not revoked from Data API roles")
    if "auth.role()" in lowered:
        fail("deprecated auth.role() must not be used")
    if "security definer" in lowered:
        fail("runtime migration must not introduce SECURITY DEFINER")
    if "runtime_recovery_execute" not in lowered:
        fail("recovery authorization action is missing")

    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    definitions = set(schema.get("$defs", {}))
    missing_definitions = EXPECTED_DEFINITIONS - definitions
    if missing_definitions:
        fail(f"missing JSON Schema definitions: {sorted(missing_definitions)}")

    openapi = yaml.safe_load(OPENAPI.read_text())
    if openapi.get("openapi") != "3.1.0":
        fail("runtime OpenAPI must be 3.1.0")
    operations = {}
    for path_item in openapi.get("paths", {}).values():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                operation_id = operation.get("operationId")
                if not operation_id:
                    fail("runtime OpenAPI operation missing operationId")
                operations[operation_id] = operation
                if operation.get("security") != [
                    {"mutualTLS": [], "bearerAuth": []}
                ]:
                    fail(f"operation {operation_id} lacks dual authentication")
    if set(operations) != EXPECTED_OPERATIONS:
        fail(
            "runtime OpenAPI operation mismatch: "
            f"expected={sorted(EXPECTED_OPERATIONS)} actual={sorted(operations)}"
        )
    schemes = openapi["components"]["securitySchemes"]
    if schemes.get("mutualTLS") != {"type": "mutualTLS"}:
        fail("mutualTLS security scheme is missing")
    if schemes.get("bearerAuth", {}).get("scheme") != "bearer":
        fail("bearerAuth security scheme is missing")

    print("Genesis Runtime Platform contracts validated successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Runtime platform validation failed: {exc}", file=sys.stderr)
        raise
