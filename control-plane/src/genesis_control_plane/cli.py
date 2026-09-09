from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

from genesis_control_plane.contracts import Command, DecisionResult, VerificationState
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.service import GovernedExecutionService
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.verifier import DockerVerifier
from genesis_control_plane.warden import Warden, WardenPolicy
from genesis_control_plane.weg import ConsumedTokenLedger, WardenExecutionGateway

STATION_ID = "GES-ALPHA-001"
ADAPTER_ID = "GEN-ADAPTER-DOCKER-001"
AUDIENCE = "WEG-GES-ALPHA-001"
CAPABILITY_RESTART = "container.instance.restart"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ges-alpha")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    restart = subparsers.add_parser("restart", help="request one governed Alpha container restart")
    restart.add_argument("--resource", required=True)
    restart.add_argument("--timeout", type=int, default=30)
    restart.add_argument("--principal", default="DM-LOCAL-OPERATOR")
    restart.add_argument("--session", default="SES-LOCAL-ALPHA")
    return parser


def _paths(environ: Mapping[str, str]) -> tuple[Path, Path, Path]:
    root = Path(__file__).resolve().parents[2]
    registry = Path(environ.get("GENESIS_REGISTRY_PATH", root / "registry" / "alpha-registry.json"))
    replay = Path(environ.get("GENESIS_REPLAY_DB", root / ".runtime" / "consumed-tokens.sqlite3"))
    river = Path(environ.get("GENESIS_RIVER_JOURNAL", root / ".runtime" / "river-evidence.jsonl"))
    return registry, replay, river


def outcome_exit_code(outcome) -> int:
    if outcome.decision.result is not DecisionResult.PERMIT:
        return 3
    if outcome.verification is None or outcome.verification.state is not VerificationState.VERIFIED:
        return 4
    return 0


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    args = build_parser().parse_args(argv)
    raw_secret = env.get("GENESIS_WARDEN_HMAC_KEY")
    if not raw_secret:
        print("GENESIS_WARDEN_HMAC_KEY is required", file=sys.stderr)
        return 2

    registry_path, replay_path, river_path = _paths(env)
    now = datetime.now(timezone.utc)
    registry = AlphaRegistry.load(registry_path)
    warden = Warden(registry, WardenPolicy())
    issuer = TokenIssuer(raw_secret.encode("utf-8"), "LOCAL-HMAC-001", AUDIENCE)
    weg = WardenExecutionGateway(registry, issuer, ConsumedTokenLedger(replay_path))
    adapter = DockerAdapter()
    service = GovernedExecutionService(
        registry=registry,
        warden=warden,
        token_issuer=issuer,
        weg=weg,
        adapter=adapter,
        verifier=DockerVerifier(adapter),
        evidence=EvidenceJournal(river_path),
    )
    command = Command(
        command_id=f"CMD-{secrets.token_hex(8)}",
        correlation_id=f"CORR-{secrets.token_hex(8)}",
        principal_id=args.principal,
        session_id=args.session,
        station_id=STATION_ID,
        adapter_id=ADAPTER_ID,
        target_resource_id=args.resource,
        capability=CAPABILITY_RESTART,
        parameters={"timeout_seconds": args.timeout},
        risk_class="medium",
        environment="alpha",
        requested_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
    )
    try:
        outcome = service.execute(command, now)
    except Exception as exc:
        print(f"governed execution failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps({
        "decision": outcome.decision.result,
        "reason": outcome.decision.reason_code,
        "token_id": outcome.token_id,
        "execution": outcome.execution.state if outcome.execution else None,
        "verification": outcome.verification.state if outcome.verification else None,
    }, separators=(",", ":")))
    return outcome_exit_code(outcome)


if __name__ == "__main__":
    raise SystemExit(main())
