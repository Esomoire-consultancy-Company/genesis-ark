from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/edge-node/v1/edge-node.schema.json"
OPENAPI = ROOT / "openapi/edge-node/v1/openapi.yaml"
MIGRATION = ROOT / "db/edge-node/v1/005_genesis_edge_node.sql"
ENGINE = ROOT / "services/edge-node/src/edge_node_service/engine.py"
AGENT = ROOT / "services/edge-node/src/edge_node_service/agent.py"
SPOOL = ROOT / "services/edge-node/src/edge_node_service/spool.py"
POSTGRES_DIR = ROOT / "services/edge-node/src/edge_node_service"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    schema = json.loads(SCHEMA.read_text())
    openapi = json.loads(OPENAPI.read_text())
    migration = MIGRATION.read_text().lower()
    engine = ENGINE.read_text()
    agent = AGENT.read_text()
    spool = SPOOL.read_text().lower()
    postgres = "\n".join(
        path.read_text()
        for path in sorted(POSTGRES_DIR.glob("postgres_*.py"))
    ).lower()

    required_defs = {
        "EnrollNodeRequest",
        "EdgeNodeIdentity",
        "HeartbeatRequest",
        "HeartbeatReceipt",
        "IssueCommandRequest",
        "EdgeCommand",
        "LeaseCommandRequest",
        "CommandLease",
        "CompleteCommandRequest",
        "SpoolEvent",
        "SpoolFlushRequest",
        "SpoolFlushReceipt",
        "EdgeEvidenceEvent",
    }
    require(required_defs <= set(schema.get("$defs", {})), "Edge Node JSON Schema is incomplete")

    required_paths = {
        "/v1/edge-nodes/enroll",
        "/v1/edge-nodes/{node_id}/heartbeats",
        "/v1/edge-nodes/{node_id}/commands",
        "/v1/edge-nodes/{node_id}/commands/lease",
        "/v1/edge-nodes/{node_id}/commands/{command_id}/complete",
        "/v1/edge-nodes/{node_id}/spool/flush",
        "/v1/edge-nodes/{node_id}",
        "/v1/edge-nodes/{node_id}/evidence",
    }
    require(required_paths <= set(openapi.get("paths", {})), "Edge Node OpenAPI paths are incomplete")
    schemes = openapi.get("components", {}).get("securitySchemes", {})
    require("bearerAuth" in schemes and "mutualTLS" in schemes, "Dual authentication schemes are missing")
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                require(
                    operation.get("security") == [{"bearerAuth": [], "mutualTLS": []}],
                    f"{method.upper()} {path} does not require bearer plus mTLS",
                )

    for fragment in (
        "create schema if not exists genesis_edge",
        "references genesis_runtime.runtime_nodes(node_id)",
        "edge_enrollment_tokens",
        "token_hash",
        "edge_node_identities",
        "last_heartbeat_sequence",
        "last_spool_sequence",
        "edge_commands",
        "lease_token_hash",
        "edge_spool_events",
        "edge_evidence_events",
        "enable row level security",
        "revoke all on all tables in schema genesis_edge from public, anon, authenticated",
        "with (security_invoker = true)",
    ):
        require(fragment in migration, f"Migration is missing: {fragment}")
    require("security definer" not in migration, "Migration must not use SECURITY DEFINER")
    require("auth.role()" not in migration, "Migration must not use deprecated auth.role() authorization")
    require("bootstrap_token text" not in migration, "Raw bootstrap tokens must not be persisted")

    require("verify_heartbeat" in engine and "HEARTBEAT_REPLAYED" in engine, "Heartbeat integrity checks are missing")
    require("capability_verifier.verify" in agent and "supervisor.execute" in agent, "Agent capability revalidation boundary is missing")
    require(
        agent.index("capability_verifier.verify") < agent.index("supervisor.execute"),
        "Capability revalidation must occur before local execution",
    )
    require("pragma journal_mode = wal" in spool, "SQLite spool must use WAL mode")
    require("pragma synchronous = full" in spool, "SQLite spool must use full synchronous durability")
    require("for update skip locked" in postgres, "PostgreSQL command leasing must use SKIP LOCKED")
    require("pg_advisory_xact_lock" in postgres, "PostgreSQL node writes must use advisory transaction locking")
    require("active_capability_grants" in postgres, "PostgreSQL capability verification must use the active grant view")

    print("Genesis Edge Node contracts validated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Edge Node contract validation failed: {exc}", file=sys.stderr)
        raise
