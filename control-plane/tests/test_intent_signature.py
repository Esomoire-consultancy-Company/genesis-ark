"""Tests for the optional real Ed25519 verification seam (also run via unittest)."""

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from genesis_control_plane.contracts import Command, DecisionResult
from genesis_control_plane.admitted_keys import FileActorKeyResolver
from genesis_control_plane.cli import main as cli_main
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.intent_signature import (
    IntentSignatureVerifier, SignedCommandIntent, intent_bytes,
)
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.service import GovernedExecutionService
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.verifier import DockerVerifier
from genesis_control_plane.warden import Warden, WardenPolicy
from genesis_control_plane.weg import ConsumedTokenLedger, WardenExecutionGateway
from genesis_control_plane.weg import WEGValidationError

NOW = datetime(2026, 9, 9, 2, 40, tzinfo=timezone.utc)
REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"


class AdmittedKeys:
    def __init__(self, public_key):
        self.public_key = public_key
        self.active = True

    def active_ed25519_key(self, principal_id, key_id, at):
        if self.active and principal_id == "DM-001" and key_id == "GENESIS-KEY-001":
            return self.public_key
        return None


class SignedIntentTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.keys = AdmittedKeys(self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ))
        self.verifier = IntentSignatureVerifier(self.keys)
        self.command = Command(
            command_id="CMD-001", correlation_id="CORR-001", principal_id="DM-001",
            session_id="SES-001", station_id="GES-ALPHA-001",
            adapter_id="GEN-ADAPTER-DOCKER-001",
            target_resource_id="RES-RIVER-WORKER-001",
            capability="container.instance.restart", parameters={"timeout_seconds": 30},
            risk_class="medium", environment="alpha", requested_at=NOW.isoformat(),
            expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        )
        self.intent = SignedCommandIntent(
            principal_id="DM-001", key_id="GENESIS-KEY-001", nonce="fresh-challenge-001",
            expires_at=(NOW + timedelta(minutes=1)).isoformat(), signature_hex="",
        )
        self.intent = replace(self.intent, signature_hex=self.private_key.sign(
            intent_bytes(self.command, self.intent)
        ).hex())
        self.registry = AlphaRegistry.load(REGISTRY)

    def test_signature_checks_exact_command_and_independent_key(self):
        self.assertIsNone(self.verifier.verify(self.command, self.intent, NOW))
        altered = replace(self.command, target_resource_id="RES-OTHER")
        self.assertEqual(self.verifier.verify(altered, self.intent, NOW), "SIGNED_INTENT_INVALID")
        self.keys.active = False
        self.assertEqual(self.verifier.verify(self.command, self.intent, NOW), "SIGNING_KEY_NOT_ADMITTED")

    def test_missing_expired_and_wider_intent_denied(self):
        self.assertEqual(self.verifier.verify(self.command, None, NOW), "SIGNED_INTENT_REQUIRED")
        self.assertEqual(self.verifier.verify(self.command, self.intent, NOW + timedelta(minutes=1)), "SIGNED_INTENT_EXPIRED")
        wide = replace(self.intent, expires_at=(NOW + timedelta(minutes=3)).isoformat())
        self.assertEqual(self.verifier.verify(self.command, wide, NOW), "SIGNED_INTENT_OUTLIVES_COMMAND")

    def test_configured_service_denies_before_token_or_docker(self):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            if args[:2] == ["docker", "restart"]:
                return SimpleNamespace(returncode=0, stdout="river-worker\n", stderr="")
            if args[:2] == ["docker", "inspect"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps([{
                    "Name": "/river-worker", "State": {"Running": True, "Health": {"Status": "healthy"}}
                }]), stderr="")
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as temp:
            issuer = TokenIssuer(b"test-secret-not-production", "KEY-TEST-001", "WEG-GES-ALPHA-001")
            adapter = DockerAdapter(runner=runner)
            service = GovernedExecutionService(
                registry=self.registry,
                warden=Warden(self.registry, WardenPolicy(), self.verifier),
                token_issuer=issuer,
                weg=WardenExecutionGateway(
                    self.registry, issuer, ConsumedTokenLedger(Path(temp) / "tokens.sqlite3"), self.verifier
                ),
                adapter=adapter, verifier=DockerVerifier(adapter),
                evidence=EvidenceJournal(Path(temp) / "river.jsonl"),
                clock=lambda: NOW,
            )
            outcome = service.execute(self.command, NOW)
            self.assertEqual(outcome.decision.result, DecisionResult.DENY)
            self.assertEqual(outcome.decision.reason_code, "SIGNED_INTENT_REQUIRED")
            self.assertIsNone(outcome.token_id)
            self.assertEqual(calls, [])
            outcome = service.execute(self.command, NOW, self.intent)
            self.assertEqual(outcome.decision.result, DecisionResult.PERMIT)
            self.assertTrue(any(args[:2] == ["docker", "restart"] for args in calls))

    def test_gateway_rechecks_revocation_and_consumes_intent_durably(self):
        issuer = TokenIssuer(b"test-secret-not-production", "KEY-TEST-001", "WEG-GES-ALPHA-001")
        warden = Warden(self.registry, WardenPolicy(), self.verifier)
        decision = warden.evaluate(self.command, NOW, self.intent)
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "tokens.sqlite3"
            gateway = WardenExecutionGateway(
                self.registry, issuer, ConsumedTokenLedger(db_path), self.verifier
            )
            token = issuer.issue(self.command, decision, NOW)
            self.keys.active = False
            with self.assertRaisesRegex(WEGValidationError, "SIGNING_KEY_NOT_ADMITTED"):
                gateway.validate_and_consume(token, self.command, NOW, self.intent)
            self.keys.active = True
            gateway.validate_and_consume(token, self.command, NOW, self.intent)
            reopened = WardenExecutionGateway(
                self.registry, issuer, ConsumedTokenLedger(db_path), self.verifier
            )
            second = issuer.issue(self.command, decision, NOW)
            with self.assertRaisesRegex(WEGValidationError, "REPLAY_DETECTED"):
                reopened.validate_and_consume(second, self.command, NOW, self.intent)
            changed = replace(self.command, command_id="CMD-002")
            signed = replace(self.intent, signature_hex=self.private_key.sign(
                intent_bytes(changed, self.intent)
            ).hex())
            changed_decision = warden.evaluate(changed, NOW, signed)
            with self.assertRaisesRegex(WEGValidationError, "REPLAY_DETECTED"):
                reopened.validate_and_consume(
                    issuer.issue(changed, changed_decision, NOW), changed, NOW, signed
                )

    def test_local_trust_snapshot_and_signed_cli_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            keys = Path(temp) / "admitted-keys.json"
            keys.write_text(json.dumps({"keys": [{
                "principal_id": "DM-001", "key_id": "GENESIS-KEY-001", "state": "active",
                "valid_from": (NOW - timedelta(minutes=1)).isoformat(),
                "valid_until": (NOW + timedelta(minutes=10)).isoformat(),
                "public_key_hex": self.keys.public_key.hex(),
            }]}))
            resolver = FileActorKeyResolver(keys)
            self.assertEqual(resolver.active_ed25519_key("DM-001", "GENESIS-KEY-001", NOW),
                             self.keys.public_key)
            data = json.loads(keys.read_text())
            data["keys"][0]["state"] = "revoked"
            keys.write_text(json.dumps(data))
            self.assertIsNone(resolver.active_ed25519_key("DM-001", "GENESIS-KEY-001", NOW))
            request = Path(temp) / "request.json"
            current = datetime.now(timezone.utc)
            fresh_command = replace(self.command, requested_at=current.isoformat(),
                                    expires_at=(current + timedelta(minutes=2)).isoformat())
            fresh_intent = replace(self.intent, expires_at=(current + timedelta(minutes=1)).isoformat())
            fresh_intent = replace(fresh_intent, signature_hex=self.private_key.sign(
                intent_bytes(fresh_command, fresh_intent)).hex())
            request.write_text(json.dumps({"command": fresh_command.__dict__,
                                           "signed_intent": fresh_intent.__dict__}))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli_main(["signed-restart", "--request", str(request)],
                    {"GENESIS_WARDEN_HMAC_KEY": "test-secret"}), 2)
            output = io.StringIO()
            with redirect_stdout(output):
                code = cli_main(["signed-restart", "--request", str(request)], {
                    "GENESIS_WARDEN_HMAC_KEY": "test-secret",
                    "GENESIS_ACTOR_KEYS_PATH": str(keys),
                    "GENESIS_REPLAY_DB": str(Path(temp) / "tokens.sqlite3"),
                    "GENESIS_RIVER_JOURNAL": str(Path(temp) / "river.jsonl"),
                })
            self.assertEqual(code, 3)
            self.assertEqual(json.loads(output.getvalue())["reason"], "SIGNING_KEY_NOT_ADMITTED")


if __name__ == "__main__":
    unittest.main()
