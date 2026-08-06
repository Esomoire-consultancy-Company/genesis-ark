from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    schema_path = ROOT / "schemas/control-tower/v1/control-tower.schema.json"
    openapi_path = ROOT / "openapi/control-tower/v1/openapi.yaml"
    migration_path = ROOT / "db/control-tower/v1/006_genesis_control_tower.sql"
    engine_paths = sorted((ROOT / "services/control-tower/src/control_tower_service").glob("engine*.py"))
    repository_paths = sorted((ROOT / "services/control-tower/src/control_tower_service").glob("postgres*.py"))
    dockerfile_path = ROOT / "services/control-tower/Dockerfile"
    docs_path = ROOT / "docs/control-tower.md"

    for path in (
        schema_path,
        openapi_path,
        migration_path,
        *engine_paths,
        *repository_paths,
        dockerfile_path,
        docs_path,
    ):
        require(path.exists(), f"missing required Control Tower artifact: {path.relative_to(ROOT)}")

    schema = json.loads(schema_path.read_text())
    openapi = yaml.safe_load(openapi_path.read_text())
    migration = migration_path.read_text().lower()
    engine = "\n".join(path.read_text() for path in engine_paths)
    repository = "\n".join(path.read_text() for path in repository_paths).lower()
    dockerfile = dockerfile_path.read_text()
    docs = docs_path.read_text()

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
    required_defs = {
        "FleetAsset",
        "Incident",
        "FleetCommand",
        "DashboardSnapshot",
        "ControlTowerEvent",
        "CapabilityAuthorization",
    }
    require(required_defs.issubset(schema.get("$defs", {})), "schema is missing canonical Control Tower objects")

    expected_paths = {
        "/v1/fleet/assets",
        "/v1/fleet/assets/{asset_id}",
        "/v1/signals",
        "/v1/incidents",
        "/v1/incidents/{incident_id}/acknowledge",
        "/v1/incidents/{incident_id}/resolve",
        "/v1/commands",
        "/v1/commands/{command_id}/approve",
        "/v1/commands/{command_id}/dispatch",
        "/v1/commands/{command_id}/complete",
        "/v1/dashboard",
        "/v1/audit/{subject_id}",
    }
    require(expected_paths.issubset(openapi.get("paths", {})), "OpenAPI is missing Control Tower operations")
    schemes = openapi.get("components", {}).get("securitySchemes", {})
    require({"bearerAuth", "mutualTLS"}.issubset(schemes), "OpenAPI must require bearer and mutual TLS")
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                security = operation.get("security", [])
                require(
                    security == [{"bearerAuth": [], "mutualTLS": []}],
                    "every Control Tower operation must require bearer and mutual TLS",
                )

    require("create schema if not exists genesis_control_tower" in migration, "private schema missing")
    tables = {
        "fleet_assets",
        "incidents",
        "operational_signals",
        "fleet_commands",
        "events",
    }
    for table in tables:
        require(f"genesis_control_tower.{table}" in migration, f"migration missing {table}")
        require(
            f"alter table genesis_control_tower.{table} enable row level security" in migration,
            f"RLS missing for {table}",
        )
    require("revoke all on all tables in schema genesis_control_tower from public, anon, authenticated" in migration, "public role revocation missing")
    require("security_invoker = true" in migration, "security-invoker views missing")
    require("security definer" not in migration, "SECURITY DEFINER is prohibited")
    require("auth.role()" not in migration, "deprecated auth.role() authorization is prohibited")
    require("where status <> 'resolved'" in migration, "active incident fingerprint guard missing")
    require("where published_at is null" in migration, "RiverOS outbox index missing")

    for token in (
        "STALE_FLEET_OBSERVATION",
        "SIGNAL_ID_CONFLICT",
        "FOUR_EYES_REQUIRED",
        "CONTROL_TOWER_COMMAND_APPROVE",
        "CONTROL_TOWER_COMMAND_DISPATCH",
        "EDGE_COMMAND_REQUESTED",
    ):
        require(token in engine, f"engine missing governed behavior: {token}")
    require("self.capability_verifier.verify" in engine, "Warden capability verification missing")
    require("request.approver_id == command.issuer_id" in engine, "independent approval check missing")

    require("pg_advisory_xact_lock" in repository, "PostgreSQL advisory locking missing")
    require("public.active_capability_grants" in repository, "active Warden grant verification missing")
    require("prepare_threshold" in repository, "transaction-pool prepared statement control missing")
    require("operational_signals" in repository, "signal idempotency persistence missing")
    require("published_at" in repository, "event outbox persistence missing")

    require(re.search(r"^USER\s+controltower$", dockerfile, re.MULTILINE) is not None, "container must run as non-root controltower user")
    require("does not create legal or operational authority" in docs, "authority boundary missing from documentation")
    require("does not:" in docs, "deployment exclusions missing from documentation")

    print("Genesis Control Tower contracts validated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
