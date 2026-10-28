"""Generate local-only, synthetic operator HTML preview without network access."""
from __future__ import annotations

import argparse
from pathlib import Path

from genesis_gateway.operator_inbox import (
    SyntheticCaseQueue, VerifiedOperator, classify_public_denial,
    record_gateway_denial, record_secret_status, render_private_preview,
)


def demo() -> SyntheticCaseQueue:
    q = SyntheticCaseQueue()
    q.ingest(classify_public_denial(event_id="PUBLIC-001", path="/.env?ignored=1", status=404,
                                   source_receipt="RAILWAY-TEST-001"))
    q.ingest(classify_public_denial(event_id="PUBLIC-002", path="/v1/intents", status=404,
                                   source_receipt="RAILWAY-TEST-002"))
    q.ingest(record_gateway_denial(event_id="DENY-001", trusted_node_id="NODE-DEMO-01",
                                   trusted_correlation_id="COR-DEMO-01", evidence_hash="a" * 64))
    q.ingest(record_secret_status(event_id="CONFIG-001", secret_reference="GENESIS_GATEWAY_API_KEY",
                                  state="rotation_due", registry_receipt_id="REGISTRY-DEMO-001"))
    return q


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline, synthetic-only operator console preview")
    parser.add_argument("--output", required=True, help="Local HTML output path")
    parser.add_argument("--role", choices=("security_custodian", "node_operator", "configuration_custodian"),
                        default="security_custodian")
    args = parser.parse_args()
    # Fixture is trusted only inside this offline example: not bound to any HTTP route.
    actor = VerifiedOperator("DIGITALME-DEMO-01", frozenset({args.role}),
                             frozenset({"NODE-DEMO-01"}), authority_verified=True, environments=frozenset({"staging"}))
    output = Path(args.output)
    output.write_text(render_private_preview(demo(), actor), encoding="utf-8")
    print("SYNTHETIC_PREVIEW_WRITTEN:" + str(output))


if __name__ == "__main__":
    main()
