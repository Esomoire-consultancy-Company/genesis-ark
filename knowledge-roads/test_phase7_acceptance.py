"""33 standalone regression checks for synthetic Phase 7 evidence acceptance."""
import base64
from datetime import datetime, timedelta, timezone
import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from phase7_acceptance import (AUDIENCE, DOMAIN, REQUIRED_ROLES, FixtureTrust,
                               Phase7AcceptanceGate, hex_digest, canonical)

NOW = datetime(2026, 11, 21, 6, 30, tzinfo=timezone.utc)

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "environment": "staging", "action": "navigate.readonly", "execute": False,
            "mutation": False, "promotion_requested": False,
            "pilot_id": "PILOT-DEMO", "run_id": "STAGING-EXERCISE-1",
            "station_id": "VSR-KS-ENGINEERING", "estate_id": "ESTATE-TEST",
            "purpose": "engineering-assurance", "commit_sha": "a" * 40,
            "route_digest": "b" * 64, "source_registry_status": "UNREGISTERED_PROPOSALS",
        }
        self.keys = {role: Ed25519PrivateKey.generate() for role in REQUIRED_ROLES}
        self.anchors = {(role, f"fixture-kid-{i}"): (f"fixture-issuer-{i}", key.public_key())
                        for i, (role, key) in enumerate(self.keys.items())}
        self.kids = {role: f"fixture-kid-{i}" for i, role in enumerate(REQUIRED_ROLES)}
        self.issuers = {role: f"fixture-issuer-{i}" for i, role in enumerate(REQUIRED_ROLES)}
        self.trust = FixtureTrust(self.anchors)
        self.gate = Phase7AcceptanceGate(self.trust)
        self.envelopes = self.mint_all()

    def plan_digest(self):
        return hex_digest({"domain": "VSR-FOR-001-R07-PLAN", "plan": self.plan})

    def payload(self, role):
        return {
            "issuer": self.issuers[role], "audience": AUDIENCE, "plan_digest": self.plan_digest(),
            "commit_sha": self.plan["commit_sha"], "route_digest": self.plan["route_digest"],
            "environment": self.plan["environment"], "run_id": self.plan["run_id"],
            "pilot_id": self.plan["pilot_id"], "station_id": self.plan["station_id"],
            "estate_id": self.plan["estate_id"], "purpose": self.plan["purpose"],
            "classification": "TEST_ONLY", "is_fixture": True, "status": "PASS",
            "evidence_id": "TEST-" + role,
            "issued_at": (NOW - timedelta(seconds=10)).isoformat(),
            "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        }

    def signed(self, role, payload=None, key=None, kid=None):
        content = {"role": role, "kid": kid or self.kids[role], "alg": "Ed25519",
                   "payload": payload if payload is not None else self.payload(role)}
        sig = (key or self.keys[role]).sign(DOMAIN + canonical(content))
        return {**content, "signature": base64.urlsafe_b64encode(sig).decode("ascii")}

    def mint_all(self):
        return {role: self.signed(role) for role in REQUIRED_ROLES}

    def check(self, expected, plan=None, envelopes=None, now=None):
        result = self.gate.evaluate(self.plan if plan is None else plan,
                                    self.envelopes if envelopes is None else envelopes,
                                    NOW if now is None else now)
        self.assertEqual(result.reason, expected)
        self.assertFalse(result.real_staging_accepted)
        self.assertFalse(result.live_navigation_authorized)
        self.assertFalse(result.engine_execution_allowed)
        self.assertFalse(result.river_receipt_emitted)
        self.assertFalse(result.merge_or_deploy_allowed)
        return result

    def replace(self, role, **modifications):
        data = dict(self.envelopes)
        data[role] = self.signed(role, {**self.payload(role), **modifications})
        return data

    def test_all_fixture_checks_pass_without_authorization(self):
        result = self.check("ALL_CHECKS_SYNTHETIC_NO_REAL_STAGING_ACCEPTANCE")
        self.assertEqual(result.disposition, "SIMULATED_ACCEPTANCE_COMPLETE")
        self.assertEqual(result.locally_verified_roles, REQUIRED_ROLES)

    def test_production_env_refused(self):
        self.check("ENVIRONMENT_OR_CAPABILITY_INVALID", plan={**self.plan, "environment": "production"})

    def test_unapproved_action_refused(self):
        self.check("ENVIRONMENT_OR_CAPABILITY_INVALID", plan={**self.plan, "action": "engine.execute"})

    def test_mutation_refused(self):
        self.check("EXECUTION_FORBIDDEN", plan={**self.plan, "mutation": True})

    def test_engine_execute_refused(self):
        self.check("EXECUTION_FORBIDDEN", plan={**self.plan, "execute": True})

    def test_missing_execute_refused(self):
        plan = dict(self.plan); del plan["execute"]
        self.check("EXECUTION_FORBIDDEN", plan=plan)

    def test_promotion_refused(self):
        self.check("PROMOTION_NOT_ALLOWED", plan={**self.plan, "promotion_requested": True})

    def test_missing_purpose_held(self):
        self.check("INCOMPLETE_ACCEPTANCE_SCOPE", plan={**self.plan, "purpose": ""})

    def test_malformed_commit_held(self):
        self.check("UNBOUND_GIT_COMMIT", plan={**self.plan, "commit_sha": "not-a-commit"})

    def test_malformed_route_digest_held(self):
        self.check("INVALID_ROUTE_DIGEST", plan={**self.plan, "route_digest": "bad"})

    def test_unspecified_registration_state_held(self):
        self.check("REGISTRATION_STATUS_NOT_PROVEN", plan={**self.plan, "source_registry_status": "ACTIVE"})

    def test_extra_plan_fields_denied(self):
        self.check("UNSUPPORTED_PLAN_FIELDS", plan={**self.plan, "hidden_engine": "run"})

    def test_missing_one_role_held(self):
        data = dict(self.envelopes); del data["RIVEROS"]
        self.check("REQUIRED_INDEPENDENT_EVIDENCE_MISSING", envelopes=data)

    def test_missing_all_roles_held(self):
        self.check("REQUIRED_INDEPENDENT_EVIDENCE_MISSING", envelopes={})

    def test_payload_mutation_invalidates_signature(self):
        data = copy.deepcopy(self.envelopes)
        data["WARDEN"]["payload"]["status"] = "PASS-BUT-MODIFIED"
        self.check("EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", envelopes=data)

    def test_unpinned_signer_denied(self):
        data = dict(self.envelopes)
        data["WARDEN"] = self.signed("WARDEN", key=Ed25519PrivateKey.generate())
        self.check("EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", envelopes=data)

    def test_claimed_real_service_not_accepted(self):
        self.check("REAL_SERVICE_ASSERTION_NOT_VERIFIED", envelopes=self.replace("GENESIS_REGISTRAR", is_fixture=False, classification="REAL"))

    def test_one_check_failed_holds(self):
        self.check("ACCEPTANCE_GATE_NOT_PASSED", envelopes=self.replace("SECURITY", status="FAIL"))

    def test_commit_mismatch_denied(self):
        self.check("EVIDENCE_SCOPE_OR_VERSION_MISMATCH", envelopes=self.replace("GENESIS_REGISTRAR", commit_sha="c" * 40))

    def test_route_mismatch_denied(self):
        self.check("EVIDENCE_SCOPE_OR_VERSION_MISMATCH", envelopes=self.replace("WARDEN", route_digest="e" * 64))

    def test_issuer_key_mismatch_denied(self):
        self.check("EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", envelopes=self.replace("DIGITALME", issuer="untrusted"))

    def test_duplicate_issuer_denied(self):
        # A different pinned key may not present an issuer already used by another role.
        data = dict(self.envelopes)
        role = "DIGITALME"
        alternate = (role, self.kids[role])
        anchors = dict(self.anchors)
        anchors[alternate] = (self.issuers["GENESIS_REGISTRAR"], self.keys[role].public_key())
        signed = self.signed(role, {**self.payload(role), "issuer": self.issuers["GENESIS_REGISTRAR"]})
        data[role] = signed
        gate = Phase7AcceptanceGate(FixtureTrust(anchors))
        result = gate.evaluate(self.plan, data, NOW)
        self.assertEqual(result.reason, "INDEPENDENCE_OR_EVIDENCE_ID_COLLISION")

    def test_duplicate_evidence_id_denied(self):
        self.check("INDEPENDENCE_OR_EVIDENCE_ID_COLLISION", envelopes=self.replace("DIGITALME", evidence_id="TEST-GENESIS_REGISTRAR"))

    def test_wrong_audience_denied(self):
        self.check("EVIDENCE_SCOPE_OR_VERSION_MISMATCH", envelopes=self.replace("WARDEN", audience="another-service"))

    def test_expired_evidence_held(self):
        self.check("EVIDENCE_EXPIRED_OR_TIME_UNTRUSTED", envelopes=self.replace("RIVEROS", expires_at=(NOW-timedelta(seconds=1)).isoformat()))

    def test_future_dated_evidence_held(self):
        self.check("EVIDENCE_EXPIRED_OR_TIME_UNTRUSTED", envelopes=self.replace("REPLAY_LEDGER", issued_at=(NOW+timedelta(seconds=1)).isoformat()))

    def test_excessive_ttl_held(self):
        self.check("EVIDENCE_EXPIRED_OR_TIME_UNTRUSTED", envelopes=self.replace("HUMAN_REVIEW", expires_at=(NOW+timedelta(hours=2)).isoformat()))

    def test_naive_clock_held(self):
        self.check("TRUSTED_CLOCK_NOT_SUPPLIED", now=datetime(2026,11,21,6,30))

    def test_no_trust_roots_denied(self):
        gate = Phase7AcceptanceGate(FixtureTrust({}))
        result = gate.evaluate(self.plan, self.envelopes, NOW)
        self.assertEqual(result.reason, "EVIDENCE_SIGNATURE_OR_ISSUER_INVALID")

    def test_duplicate_signer_root_rejected(self):
        anchors = dict(self.anchors)
        anchors[("DIGITALME", self.kids["DIGITALME"])] = (
            self.issuers["DIGITALME"], self.keys["GENESIS_REGISTRAR"].public_key())
        with self.assertRaises(ValueError):
            FixtureTrust(anchors)

    def test_corrupted_signature_denied(self):
        data = copy.deepcopy(self.envelopes)
        data["RIVEROS"]["signature"] = "garbage"
        self.check("EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", envelopes=data)

    def test_wrong_role_denied(self):
        data = copy.deepcopy(self.envelopes)
        data["DIGITALME"]["role"] = "WARDEN"
        self.check("EVIDENCE_SIGNATURE_OR_ISSUER_INVALID", envelopes=data)

    def test_all_complete_cannot_approve_merge_or_deploy(self):
        r = self.gate.evaluate(self.plan,self.envelopes,NOW)
        self.assertFalse(any((r.real_staging_accepted,r.merge_or_deploy_allowed,r.engine_execution_allowed)))

if __name__ == "__main__":
    unittest.main()
