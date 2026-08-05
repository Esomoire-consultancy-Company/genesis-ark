from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"control-tower validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_text(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            fail(f"{path.relative_to(ROOT)} is missing {needle!r}")


def main() -> None:
    openapi_path = ROOT / "openapi/control-tower/v1/openapi.yaml"
    schema_path = ROOT / "schemas/control-tower/v1/control-tower.schema.json"
    migration_path = ROOT / "db/control-tower/v1/006_genesis_control_tower.sql"
    engine_path = ROOT / "services/control-tower/src/control_tower_service/engine.py"
    repository_path = ROOT / "services/control-tower/src/control_tower_service/postgres_repository.py"
    repository_paths = list((ROOT / "services/control-tower/src/control_tower_service").glob("postgres_*.py"))
    dockerfile_path = ROOT / "services/control-tower/Dockerfile"

    for path in [openapi_path, schema_path, migration_path, engine_path, repository_path, dockerfile_path]:
        if not path.exists():
            fail(f"missing {path.relative_to(ROOT)}")

    openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    required_paths = {
        "/v1/control-tower/fleet/refresh",
        "/v1/control-tower/fleet",
        "/v1/control-tower/nodes/{node_id}",
        "/v1/control-tower/command-requests",
        "/v1/control-tower/command-requests/{request_id}/authorize",
        "/v1/control-tower/command-requests/{request_id}/dispatch",
        "/v1/control-tower/incidents",
        "/v1/control-tower/incidents/{incident_id}/transition",
        "/v1/control-tower/publications/lease",
        "/v1/control-tower/publications/{lease_id}/ack",
        "/v1/control-tower/dashboard",
    }
    missing_paths = required_paths - set(openapi.get("paths", {}))
    if missing_paths:
        fail(f"OpenAPI is missing paths: {sorted(missing_paths)}")
    schemes = openapi.get("components", {}).get("securitySchemes", {})
    if not {"bearerAuth", "mutualTLS"}.issubset(schemes):
        fail("OpenAPI must define bearerAuth and mutualTLS")
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            security = operation.get("security", [])
            if {"bearerAuth": [], "mutualTLS": []} not in security:
                fail(f"{method.upper()} {path} does not require both authentication schemes")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    definitions = schema.get("$defs", {})
    expected_defs = {
        "FleetNodeSnapshot",
        "ControlCommandRequest",
        "ControlIncident",
        "PublicationLease",
        "DashboardSummary",
        "ControlTowerEvent",
    }
    if not expected_defs.issubset(definitions):
        fail(f"JSON Schema is missing definitions: {sorted(expected_defs - set(definitions))}")

    require_text(
        migration_path,
        [
            "create schema if not exists genesis_control_tower",
            "create table genesis_control_tower.fleet_node_snapshots",
            "create table genesis_control_tower.command_requests",
            "create table genesis_control_tower.incidents",
            "create table genesis_control_tower.publication_leases",
            "create table genesis_control_tower.publication_claims",
            "enable row level security",
            "revoke all on all tables in schema genesis_control_tower from public, anon, authenticated",
            "with (security_invoker = true)",
        ],
    )
    migration = migration_path.read_text(encoding="utf-8").lower()
    if "security definer" in migration or "auth.role()" in migration:
        fail("migration contains a forbidden authorization pattern")

    require_text(
        engine_path,
        [
            "self.capability_verifier.verify(",
            "CONTROL_COMMAND_AUTHORIZED",
            "CONTROL_COMMAND_DISPATCHED",
            "NODE_QUARANTINED",
        ],
    )
    if engine_path.read_text(encoding="utf-8").count("self.capability_verifier.verify(") < 2:
        fail("command authorization and dispatch must each verify capability state")

    repository_text = "\n".join(path.read_text(encoding="utf-8") for path in repository_paths)
    for needle in [
            "pg_advisory_xact_lock",
            "public.active_capability_grants",
            "genesis_runtime.runtime_events",
            "genesis_edge.edge_evidence_events",
            "genesis_control_tower.control_tower_events",
            "genesis_edge.edge_commands",
            "publication_claims",
            "PUBLICATION_ACK_SET_MISMATCH",
        ]:
        if needle not in repository_text:
            fail(f"PostgreSQL adapter is missing {needle!r}")
    require_text(dockerfile_path, ["USER 10001", "genesis-control-tower"])

    print("Genesis Control Tower contracts: passed")


if __name__ == "__main__":
    main()
