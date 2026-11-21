"""Local R0.6 cryptographic staging fixture tests; never live authority."""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from phase6_trust import (AUDIENCE, DOMAIN, KINDS, StagingTrust, DurableReplay,
                          VerifiedStagingNavigator, canonical)

NOW = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)


class TrustTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.dbfile = Path(self.tempdir.name) / "replay.sqlite3"
        self.keys = {k: Ed25519PrivateKey.generate() for k in KINDS}
        self.issuers = dict(zip(KINDS, ["GENESIS-STAGING-ROOT", "DIGITALME-STAGING-ROOT",
                                       "WARDEN-STAGING-ROOT", "RIVER-STAGING-ROOT"]))
        self.kids = {kind: "fixture-" + kind.lower() for kind in KINDS}
        roots = {(k, self.kids[k]): (self.issuers[k], self.keys[k].public_key()) for k in KINDS}
        self.trust = StagingTrust(roots)
        self.gate = VerifiedStagingNavigator(self.trust, DurableReplay(self.dbfile))
        self.intent = dict(request_id="REQ-001", principal_id="DM-001", session_id="SESSION-001",
                           estate_id="ESTATE-001", station_id="STATION-001", location_id="LOC-001",
                           purpose="village-planning", capability="navigate.readonly",
                           execute=False, mutation=False, steps=["FOR-0001", "FOR-0003"],
                           expires_at=(NOW + timedelta(seconds=100)).isoformat())
        self.registry = dict(issuer=self.issuers[KINDS[0]], audience=AUDIENCE, station_id="STATION-001",
                             snapshot_id="SNAP-001", revoked=False, issued_at=NOW.isoformat(),
                             expires_at=(NOW + timedelta(seconds=100)).isoformat(),
                             objects={s: {"state": "ACTIVE", "revoked": False, "genesis_id": "REG-" + s,
                                          "version": "1.0.0", "source_ref": "SOURCE-" + s,
                                          "attestation_ref": "ATT-" + s, "station_ids": ["STATION-001"],
                                          "engine_execution_allowed": False} for s in self.intent["steps"]})
        self.identity = dict(issuer=self.issuers[KINDS[1]], audience=AUDIENCE, verified=True,
                             revoked=False, consent=True, mandate=True, capability="navigate.readonly",
                             issued_at=NOW.isoformat(),
                             expires_at=(NOW + timedelta(seconds=100)).isoformat(),
                             **{k: self.intent[k] for k in ("principal_id", "session_id", "estate_id", "station_id", "location_id", "purpose")})
        self.warden = dict(issuer=self.issuers[KINDS[2]], audience=AUDIENCE,
                           decision="PERMIT", capability="navigate.readonly", revoked=False,
                           policy_id="POL-STAGING", policy_version="0.1.0", decision_id="WD-001",
                           nonce="long-unique-test-nonce-01", issued_at=NOW.isoformat(),
                           expires_at=(NOW + timedelta(seconds=50)).isoformat(),
                           **{k: self.intent[k] for k in ("principal_id", "session_id", "estate_id", "station_id", "location_id", "purpose")})
        self.river = dict(issuer=self.issuers[KINDS[3]], audience=AUDIENCE, classification="TEST_ONLY",
                          status="SIMULATED_ACK", fixture_receipt_id="RIVER-TEST-001",
                          decision_id="WD-001", issued_at=NOW.isoformat(),
                          expires_at=(NOW + timedelta(seconds=50)).isoformat())

    def sign(self, kind, payload):
        signed = {"kind": kind, "alg": "Ed25519", "kid": self.kids[kind], "payload": payload}
        sig = self.keys[kind].sign(DOMAIN + canonical(signed))
        return {**signed, "signature": base64.urlsafe_b64encode(sig).decode("ascii")}

    def envelopes(self):
        from phase6_trust import fingerprint
        route_digest = fingerprint({"domain": "VSR-FOR-001-R06-ROUTE",
            "scope": {k: self.intent[k] for k in ("principal_id", "session_id", "estate_id", "station_id", "location_id", "purpose")},
            "request_id": self.intent["request_id"], "capability": "navigate.readonly",
            "snapshot_id": self.registry["snapshot_id"],
            "frameworks": [{"framework": s, **{k: self.registry["objects"][s][k] for k in
                ("genesis_id", "version", "source_ref", "attestation_ref")}} for s in self.intent["steps"]]})
        self.warden["route_digest"] = route_digest
        self.warden["identity_digest"] = fingerprint(self.identity)
        self.river["route_digest"] = route_digest
        return {"genesis": self.sign(KINDS[0], self.registry),
                "digitalme": self.sign(KINDS[1], self.identity),
                "warden": self.sign(KINDS[2], self.warden),
                "river": self.sign(KINDS[3], self.river)}

    def run_case(self, expected, env=None, intent=None):
        outcome = self.gate.evaluate(self.intent if intent is None else intent,
                                     self.envelopes() if env is None else env, NOW)
        self.assertEqual(outcome.reason, expected)
        self.assertFalse(outcome.authority_granted)
        self.assertFalse(outcome.engine_execution_allowed)
        self.assertFalse(outcome.real_river_receipt_emitted)
        return outcome

    def test_passed_staging_is_not_real_authority(self):
        r = self.run_case("NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT")
        self.assertEqual(r.disposition, "STAGING_CRYPTO_VERIFIED_ONLY")
        self.assertTrue(r.simulated_ack_recorded)

    def test_replay_survives_new_database_instance(self):
        self.run_case("NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT")
        self.gate = VerifiedStagingNavigator(self.trust, DurableReplay(self.dbfile))
        self.run_case("REPLAY_DETECTED")

    def test_same_decision_different_nonce_remains_one_shot(self):
        self.run_case("NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT")
        self.warden["nonce"] = "another-valid-nonce-02"
        self.run_case("REPLAY_DETECTED")

    def test_default_trust_store_has_no_keys(self):
        self.gate = VerifiedStagingNavigator(StagingTrust({}), DurableReplay(self.dbfile))
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED")

    def test_missing_signed_fixture(self):
        e = self.envelopes(); del e["warden"]
        self.run_case("SIGNED_FIXTURE_MISSING", env=e)

    def test_unknown_key_fails(self):
        e = self.envelopes(); e["genesis"]["kid"] = "random-key"
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED", env=e)

    def test_wrong_issuer_fails_even_if_signed(self):
        self.registry["issuer"] = "ATTACKER"
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED")

    def test_wrong_algorithm_fails(self):
        e = self.envelopes(); e["genesis"]["alg"] = "none"
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED", env=e)

    def test_changed_signed_payload_fails(self):
        e = self.envelopes(); e["genesis"]["payload"] = {**e["genesis"]["payload"], "snapshot_id": "CHANGED"}
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED", env=e)

    def test_corrupted_signature_fails(self):
        e = self.envelopes(); e["genesis"]["signature"] = "invalid!"
        self.run_case("REGISTRY_SIGNATURE_UNTRUSTED", env=e)

    def test_intent_engine_denied(self):
        self.run_case("READONLY_CAPABILITY_ONLY", intent={**self.intent, "execute": True})

    def test_intent_mutation_missing_denied(self):
        altered = dict(self.intent); del altered["mutation"]
        self.run_case("READONLY_CAPABILITY_ONLY", intent=altered)

    def test_intent_expired(self):
        self.run_case("INTENT_TIME_INVALID", intent={**self.intent,
            "expires_at": (NOW - timedelta(seconds=1)).isoformat()})

    def test_intent_no_purpose(self):
        self.run_case("INTENT_SCOPE_INCOMPLETE", intent={**self.intent, "purpose": ""})

    def test_duplicate_steps_denied(self):
        self.run_case("DUPLICATE_STEPS", intent={**self.intent, "steps": ["FOR-0001", "FOR-0001"]})

    def test_registry_station_denied(self):
        self.registry["station_id"] = "STATION-OTHER"
        self.run_case("REGISTRY_SCOPE_MISMATCH")

    def test_registry_revocation_held(self):
        self.registry["revoked"] = True
        self.run_case("REGISTRY_SNAPSHOT_NOT_VALID")

    def test_framework_revocation_held(self):
        self.registry["objects"]["FOR-0001"]["revoked"] = True
        self.run_case("FRAMEWORK_NOT_ACTIVE")

    def test_framework_provenance_missing(self):
        self.registry["objects"]["FOR-0001"]["attestation_ref"] = ""
        self.run_case("FRAMEWORK_PROVENANCE_INCOMPLETE")

    def test_framework_wrong_station(self):
        self.registry["objects"]["FOR-0001"]["station_ids"] = ["STATION-OTHER"]
        self.run_case("FRAMEWORK_STATION_DENIED")

    def test_engine_marked_executable_denied(self):
        self.registry["objects"]["FOR-0001"]["engine_execution_allowed"] = True
        self.run_case("FRAMEWORK_ENGINE_SCOPE_DENIED")

    def test_identity_wrong_principal(self):
        self.identity["principal_id"] = "PRINCIPAL-OTHER"
        self.run_case("IDENTITY_SCOPE_MISMATCH")

    def test_identity_consent_revoked(self):
        self.identity["consent"] = False
        self.run_case("CONSENT_OR_MANDATE_DENIED")

    def test_identity_mandate_denied(self):
        self.identity["mandate"] = False
        self.run_case("CONSENT_OR_MANDATE_DENIED")

    def test_identity_signature_untrusted(self):
        e = self.envelopes(); e["digitalme"]["signature"] = "bad"
        self.run_case("IDENTITY_SIGNATURE_UNTRUSTED", env=e)

    def test_warden_route_mismatch(self):
        self.warden["route_digest"] = "INCORRECT"
        e = self.envelopes()
        e["warden"]["payload"] = {**self.warden, "route_digest": "INCORRECT"}
        e["warden"] = self.sign(KINDS[2], e["warden"]["payload"])
        self.run_case("WARDEN_DECISION_MISMATCH", env=e)

    def test_warden_identity_binding(self):
        e = self.envelopes()
        payload = {**e["warden"]["payload"], "identity_digest": "INCORRECT"}
        e["warden"] = self.sign(KINDS[2], payload)
        self.run_case("WARDEN_DECISION_MISMATCH", env=e)

    def test_warden_wrong_audience(self):
        e = self.envelopes(); e["warden"] = self.sign(KINDS[2], {**e["warden"]["payload"], "audience": "LIVE"})
        self.run_case("WARDEN_SCOPE_MISMATCH", env=e)

    def test_warden_short_nonce(self):
        e = self.envelopes(); e["warden"] = self.sign(KINDS[2], {**e["warden"]["payload"], "nonce": "short"})
        self.run_case("WARDEN_DECISION_EXPIRED", env=e)

    def test_warden_outlives_intent(self):
        e = self.envelopes(); e["warden"] = self.sign(KINDS[2], {**e["warden"]["payload"],
            "expires_at": (NOW + timedelta(seconds=110)).isoformat()})
        self.run_case("WARDEN_OUTLIVES_INTENT", env=e)

    def test_river_fake_production_receipt_rejected(self):
        e = self.envelopes(); e["river"] = self.sign(KINDS[3], {**e["river"]["payload"], "classification": "PRODUCTION"})
        self.run_case("RIVER_FIXTURE_NOT_MATCHED", env=e)

    def test_river_mismatched_decision_id(self):
        e = self.envelopes(); e["river"] = self.sign(KINDS[3], {**e["river"]["payload"], "decision_id": "DIFFERENT"})
        self.run_case("RIVER_FIXTURE_NOT_MATCHED", env=e)

    def test_river_signature_corrupted(self):
        e = self.envelopes(); e["river"]["signature"] = "!"
        self.run_case("RIVER_FIXTURE_SIGNATURE_UNTRUSTED", env=e)

    def test_provenance_change_changes_route_digest(self):
        first = self.run_case("NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT").route_digest
        self.registry["objects"]["FOR-0001"]["source_ref"] = "NEW-PAPER-REF"
        self.warden["decision_id"] = "WD-002"; self.warden["nonce"] = "long-unique-test-nonce-02"
        self.river["decision_id"] = "WD-002"
        second = self.run_case("NO_LIVE_AUTHORITY_OR_RIVER_RECEIPT").route_digest
        self.assertNotEqual(first, second)

    def test_memory_replay_store_forbidden(self):
        with self.assertRaises(ValueError):
            DurableReplay(":memory:")

    def test_naive_clock_held(self):
        self.assertEqual(self.gate.evaluate(self.intent, self.envelopes(),
                                          datetime(2026, 11, 21, 8, 0)).reason, "UNTRUSTED_CLOCK")

if __name__ == "__main__":
    unittest.main()