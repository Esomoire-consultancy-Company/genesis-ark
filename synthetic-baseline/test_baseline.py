"""Synthetic-only, no-network tests; no third-party packages."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import SyntheticOracle, digest, load_manifest, validate_manifest
from verify import run


class SyntheticBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_manifest()

    def request(self, actor="SYN-ACTOR-CREATOR-01", action="creator.draft.synthetic", **extra):
        return {"request_id": "SYN-REQ-TEST-001", "actor_id": actor,
                "action": action, "environment": "synthetic-ci", **extra}

    def test_full_scenario_matrix(self):
        self.assertEqual(len(run()), 17)

    def test_no_external_effects_even_on_allow(self):
        oracle = SyntheticOracle(self.fixture)
        self.assertEqual(oracle.evaluate(self.request())["decision"], "ALLOW")
        self.assertEqual(oracle.effects, 0)

    def test_no_external_effects_even_on_escalate(self):
        oracle = SyntheticOracle(self.fixture)
        receipt = oracle.evaluate(self.request(actor="SYN-ACTOR-OPERATOR-01",
                         action="node.service.promote.synthetic"))
        self.assertEqual(receipt["decision"], "ESCALATE")
        self.assertEqual(receipt["executable"], False)
        self.assertEqual(oracle.effects, 0)

    def test_same_request_replay_is_deterministic(self):
        oracle = SyntheticOracle(self.fixture)
        first = oracle.evaluate(self.request())
        second = oracle.evaluate(self.request())
        self.assertEqual(first, second)
        self.assertEqual(first["evidence_sha256"], digest({k:v for k,v in first.items()
                           if k != "evidence_sha256"}))

    def test_same_request_id_changed_payload_fails_closed(self):
        oracle = SyntheticOracle(self.fixture)
        oracle.evaluate(self.request())
        with self.assertRaisesRegex(ValueError, "replay conflict"):
            oracle.evaluate(self.request(action="node.service.promote.synthetic"))

    def test_authority_injection_is_rejected(self):
        oracle = SyntheticOracle(self.fixture)
        with self.assertRaisesRegex(ValueError, "unexpected request fields"):
            oracle.evaluate(self.request(decision="ALLOW"))

    def test_unknown_request_field_rejected(self):
        oracle = SyntheticOracle(self.fixture)
        with self.assertRaises(ValueError):
            oracle.evaluate(self.request(root_override=True))

    def test_missing_synthetic_request_id_fails(self):
        oracle = SyntheticOracle(self.fixture)
        with self.assertRaises(ValueError):
            oracle.evaluate({"actor_id":"SYN-ACTOR-CREATOR-01",
                             "action":"creator.draft.synthetic","environment":"synthetic-ci"})

    def test_non_synthetic_actor_in_manifest_rejected(self):
        m = copy.deepcopy(self.fixture)
        m["actors"][0]["id"] = "REAL-USER-001"
        with self.assertRaisesRegex(ValueError, "live-looking"):
            validate_manifest(m)

    def test_non_synthetic_licence_rejected(self):
        m = copy.deepcopy(self.fixture)
        m["licences"][0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "not explicitly synthetic"):
            validate_manifest(m)

    def test_real_world_action_in_fixture_rejected(self):
        m = copy.deepcopy(self.fixture)
        m["action_policies"][0]["action"] = "production.settle"
        with self.assertRaisesRegex(ValueError, "non-synthetic capability"):
            validate_manifest(m)

    def test_credentials_and_personal_fields_rejected(self):
        for forbidden in ("secret", "email", "token", "api_key", "password", "phone"):
            m = copy.deepcopy(self.fixture)
            m["actors"][0][forbidden] = "placeholder"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "credential or personal"):
                    validate_manifest(m)

    def test_duplicate_actor_rejected(self):
        m = copy.deepcopy(self.fixture)
        m["actors"].append(dict(m["actors"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate actors"):
            validate_manifest(m)

    def test_missing_licence_denied(self):
        m = copy.deepcopy(self.fixture)
        m["licences"] = [lic for lic in m["licences"] if lic["actor_id"] != "SYN-ACTOR-CREATOR-01"]
        receipt = SyntheticOracle(m).evaluate(self.request())
        self.assertEqual((receipt["decision"], receipt["reason_code"]),
                         ("DENY", "SYNTHETIC_LICENCE_MISSING"))

    def test_licence_is_not_real_authority(self):
        oracle = SyntheticOracle(self.fixture)
        receipt = oracle.evaluate(self.request(environment="production"))
        self.assertEqual(receipt["decision"], "DENY")
        self.assertFalse(receipt["executable"])

    def test_individual_cannot_quote_without_commons_membership(self):
        oracle = SyntheticOracle(self.fixture)
        receipt = oracle.evaluate(self.request(actor="SYN-ACTOR-NONMEMBER-01",
                         action="subscription.quote.synthetic", node_id="SYN-ORG-BNR-01",
                         legal_supplier_id="SYN-ORG-SUPPLIER-01"))
        self.assertEqual(receipt["reason_code"], "COMMONS_MEMBERSHIP_REQUIRED")

    def test_legal_supplier_cannot_be_swapped(self):
        oracle = SyntheticOracle(self.fixture)
        receipt = oracle.evaluate(self.request(actor="SYN-ACTOR-REP-01",
                         action="subscription.quote.synthetic", node_id="SYN-ORG-BNR-01",
                         legal_supplier_id="SYN-ORG-BNR-01"))
        self.assertEqual(receipt["reason_code"], "LEGAL_SUPPLIER_DENIED")

    def test_licence_supplier_binding_mismatch_fails(self):
        m = copy.deepcopy(self.fixture)
        m["organizations"].append({"id":"SYN-ORG-SUPPLIER-02","kind":"legal_supplier",
                                   "name":"Other fictional supplier"})
        oracle = SyntheticOracle(m)
        receipt = oracle.evaluate(self.request(actor="SYN-ACTOR-REP-01",
                         action="subscription.quote.synthetic", node_id="SYN-ORG-BNR-01",
                         legal_supplier_id="SYN-ORG-SUPPLIER-02"))
        self.assertEqual(receipt["reason_code"], "LICENCE_SCOPE_MISMATCH")

    def test_fixture_uses_frozen_clock(self):
        self.assertEqual(self.fixture["test_clock"], "2026-10-28T10:00:00Z")

    def test_fixture_has_no_real_sso_or_payments(self):
        text = json.dumps(self.fixture).lower()
        for word in ("https://", "http://", "sk-proj-", "@gmail.com", "settle.synthetic"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()


class FixtureLockTests(unittest.TestCase):
    def test_canonical_fixture_hashes_are_locked(self):
        from fixture_lock import verify_lock
        lock = verify_lock()
        self.assertEqual(set(lock["sha256"]), {"fixtures.json", "scenarios.json"})

    def test_fixture_tamper_detection(self):
        import hashlib
        from fixture_lock import hashes, verify_lock
        real_hashes = hashes()
        self.assertTrue(all(len(v) == 64 and int(v, 16) >= 0 for v in real_hashes.values()))
        self.assertEqual(verify_lock()["sha256"], real_hashes)
