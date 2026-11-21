"""VSR-FOR-001 R0.4 sandbox verification tests. No real authority."""
import copy
from datetime import datetime, timedelta, timezone
import unittest
from admission_contract import SandboxWardenGate, prepare_route, sign_sandbox_claims, digest


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
        self.route = dict(route_id="VSR-ROUTE-DEMO-001", principal_id="FIXTURE-P1",
                          estate_id="FIXTURE-ESTATE-1", station_id="VSR-KS-PLANNING",
                          purpose="training", capability="navigate.readonly",
                          steps=["FOR-0001", "FOR-0003"])
        self.registrations = {
            step: dict(registration_state="ACTIVE", external_registry_id="FIXTURE-REG-" + step,
                       framework_version="0.1.0", attestation_ref="FIXTURE-ATTEST-" + step,
                       source_ref="FIXTURE-SOURCE-" + step,
                       knowledge_station_ids=["VSR-KS-PLANNING"])
            for step in self.route["steps"]}
        self.secret = b"SAMPLE-SANDBOX-ONLY-SECRET-NOT-FOR-PRODUCTION-000001"
        self.prepared = prepare_route(self.route, self.registrations)
        self.claims = dict(audience="vsr.knowledge-roads.sandbox", capability="navigate.readonly",
                           decision="PERMIT", policy_id="VSR-NAV-READONLY-SANDBOX-R0.4",
                           route_digest=self.prepared.route_digest,
                           principal_id=self.route["principal_id"], estate_id=self.route["estate_id"],
                           station_id=self.route["station_id"], purpose=self.route["purpose"],
                           decision_id="WD-FIXTURE-1", nonce="SANDBOX-UNIQUE-NONCE-1",
                           issued_at=self.now.isoformat(),
                           expires_at=(self.now + timedelta(seconds=60)).isoformat())

    def signed(self, claims=None):
        return sign_sandbox_claims(self.claims if claims is None else claims, self.secret)

    def assess(self, claims=None, route=None, prepared=None, signed=None):
        return SandboxWardenGate(self.secret).assess(
            self.prepared if prepared is None else prepared,
            self.route if route is None else route,
            self.claims if claims is None else claims,
            self.signed() if signed is None else signed, self.now)

    def test_preparation_never_grants_authority(self):
        self.assertEqual(self.prepared.disposition, "READY_FOR_SANDBOX")
        self.assertFalse(self.prepared.authority_granted)
        self.assertFalse(self.prepared.execution_allowed)
        self.assertFalse(self.prepared.river_receipt_emitted)

    def test_no_proposed_registration_as_live(self):
        registry = copy.deepcopy(self.registrations)
        registry["FOR-0001"]["registration_state"] = "PROPOSED_LOCAL_ONLY"
        self.assertEqual(prepare_route(self.route, registry).disposition, "HOLD")

    def test_missing_registry_held(self):
        self.assertEqual(prepare_route(self.route, {}).disposition, "HOLD")

    def test_missing_source_attestation_held(self):
        r = copy.deepcopy(self.registrations)
        r["FOR-0001"]["attestation_ref"] = None
        self.assertEqual(prepare_route(self.route, r).disposition, "HOLD")

    def test_cross_station_denied(self):
        route = dict(self.route, station_id="VSR-KS-RESTRICTED")
        self.assertEqual(prepare_route(route, self.registrations).reason,
                         "KNOWLEDGE_STATION_SCOPE_MISMATCH")

    def test_execute_denied(self):
        self.assertEqual(prepare_route(dict(self.route, execute=True), self.registrations).disposition, "DENY")

    def test_unapproved_capability_denied(self):
        self.assertEqual(prepare_route(dict(self.route, capability="container.instance.restart"),
                                       self.registrations).disposition, "DENY")

    def test_invalid_route_denied(self):
        self.assertEqual(prepare_route(dict(self.route, steps=[]), self.registrations).disposition, "DENY")
        self.assertEqual(prepare_route(dict(self.route, steps=["FOR-0001"]*2), self.registrations).disposition, "DENY")

    def test_deterministic_digest(self):
        self.assertEqual(self.prepared.route_digest, prepare_route(self.route, self.registrations).route_digest)
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_version_change_rebinds_digest(self):
        reg = copy.deepcopy(self.registrations)
        reg["FOR-0001"]["framework_version"] = "0.2.0"
        self.assertNotEqual(self.prepared.route_digest, prepare_route(self.route, reg).route_digest)

    def test_sandbox_fixture_permit_is_not_authority(self):
        result = self.assess()
        self.assertEqual(result.disposition, "SIMULATED_PERMIT")
        self.assertFalse(result.authority_granted)
        self.assertFalse(result.execution_allowed)
        self.assertFalse(result.river_receipt_emitted)

    def test_signature_tampering_denied(self):
        claims = dict(self.claims, purpose="secret-extraction")
        self.assertEqual(self.assess(claims=claims, signed=self.signed()).disposition, "DENY")

    def test_validly_signed_wrong_scope_denied(self):
        claims = dict(self.claims, estate_id="FIXTURE-ESTATE-OTHER")
        self.assertEqual(self.assess(claims=claims).reason, "SANDBOX_SCOPE_MISMATCH")

    def test_stale_decision_denied(self):
        claims = dict(self.claims, issued_at=(self.now-timedelta(minutes=10)).isoformat(),
                      expires_at=(self.now-timedelta(minutes=9)).isoformat())
        self.assertEqual(self.assess(claims=claims).disposition, "DENY")

    def test_expiry_window_denied(self):
        claims = dict(self.claims, expires_at=(self.now + timedelta(hours=5)).isoformat())
        self.assertEqual(self.assess(claims=claims).reason, "SANDBOX_TTL_INVALID")

    def test_replay_denied(self):
        gate = SandboxWardenGate(self.secret)
        signed = self.signed()
        self.assertEqual(gate.assess(self.prepared,self.route,self.claims,signed,self.now).disposition,"SIMULATED_PERMIT")
        self.assertEqual(gate.assess(self.prepared,self.route,self.claims,signed,self.now).reason,"SANDBOX_REPLAY_DENIED")

    def test_route_tampering_denied(self):
        self.assertEqual(self.assess(route=dict(self.route, purpose="payment")).reason,"ROUTE_CONTEXT_CHANGED")

    def test_post_preparation_step_swap_denied(self):
        altered = dict(self.route, steps=["FOR-0003", "FOR-0001"])
        self.assertEqual(self.assess(route=altered).reason, "ROUTE_CONTEXT_CHANGED")

    def test_post_preparation_mutation_denied(self):
        altered = dict(self.route, mutation=True)
        self.assertEqual(self.assess(route=altered).reason, "EXECUTION_NOT_ALLOWED")

    def test_malformed_station_binding_held(self):
        registry = copy.deepcopy(self.registrations)
        registry["FOR-0001"]["knowledge_station_ids"] = None
        self.assertEqual(prepare_route(self.route, registry).reason, "MALFORMED_STATION_BINDING")

    def test_source_change_rebinds_digest(self):
        registry = copy.deepcopy(self.registrations)
        registry["FOR-0001"]["source_ref"] = "FIXTURE-SOURCE-UPDATED"
        self.assertNotEqual(self.prepared.route_digest,
                            prepare_route(self.route, registry).route_digest)

    def test_no_sandbox_key_too_short(self):
        with self.assertRaises(ValueError):
            SandboxWardenGate(b"weak")

    def test_naive_clock_denied(self):
        gate = SandboxWardenGate(self.secret)
        self.assertEqual(gate.assess(self.prepared,self.route,self.claims,self.signed(),
                                     datetime(2026,11,21,9,0)).reason,"CLOCK_NOT_TIMEZONE_AWARE")

    def test_absent_proposal_not_admitted_even_if_signed(self):
        prepared = prepare_route(self.route,{})
        self.assertEqual(self.assess(prepared=prepared).disposition,"HOLD")


if __name__ == "__main__":
    unittest.main()
