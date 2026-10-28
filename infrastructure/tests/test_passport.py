import copy
import json
import unittest
from pathlib import Path

from infrastructure.passport import PassportError, validate_passport

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "synthetic-ark-001.json"


class PassportTests(unittest.TestCase):
    def setUp(self):
        self.node = json.loads(SAMPLE.read_text(encoding="utf-8"))

    def test_synthetic_ark_field_review_not_commissioned(self):
        response = validate_passport(self.node)
        self.assertEqual(response["mode"], "ARK")
        self.assertTrue(response["physical_bound"])
        self.assertTrue(response["digital_bound"])
        self.assertFalse(response["execution_enabled"])
        self.assertFalse(response["physically_commissioned"])
        self.assertFalse(response["independently_witnessed"])

    def test_cannot_enable_remote_execution(self):
        self.node["execution_enabled"] = True
        with self.assertRaisesRegex(PassportError, "REMOTE_EXECUTION"):
            validate_passport(self.node)

    def test_cannot_register_real_node_using_synthetic_validator(self):
        self.node["synthetic_only"] = False
        with self.assertRaisesRegex(PassportError, "SYNTHETIC_ONLY"):
            validate_passport(self.node)

    def test_ark_cannot_inherit_takeover(self):
        self.node["authority_evidence_ids"] = ["TAKEOVER-SYNTHETIC-001"]
        with self.assertRaisesRegex(PassportError, "ARK_DOES_NOT_TRANSFER_CONTROL"):
            validate_passport(self.node)

    def test_arc_requires_separate_intervention_authority(self):
        self.node["mode"] = "ARC"
        with self.assertRaisesRegex(PassportError, "ARC_REQUIRES_SPECIFIC"):
            validate_passport(self.node)
        self.node["authority_evidence_ids"] = ["ARC-AUTH-SYNTHETIC-001"]
        self.assertEqual(validate_passport(self.node)["mode"], "ARC")

    def test_no_physical_ark_without_location_and_asset(self):
        self.node["location_ref"] = None
        with self.assertRaisesRegex(PassportError, "PHYSICAL_SITE"):
            validate_passport(self.node)

    def test_active_state_requires_both_physical_digital_acceptance(self):
        self.node["status"] = "active"
        with self.assertRaisesRegex(PassportError, "AUTHORITY_AND_WARDEN"):
            validate_passport(self.node)
        self.node.update(warden_policy_id="WARDEN-SYNTHETIC-001",
                         physical_acceptance_id="ACCEPT-PHYSICAL-001",
                         digital_acceptance_id="ACCEPT-DIGITAL-001",
                         river_receipt_ids=["RIVER-SYNTHETIC-001"])
        output = validate_passport(self.node)
        self.assertFalse(output["physically_commissioned"])  # No synthetic schema may certify reality.

    def test_digital_only_no_physical_site_claim(self):
        self.node["mode"] = "DIGITAL"
        with self.assertRaisesRegex(PassportError, "DIGITAL_ONLY"):
            validate_passport(self.node)
        self.node["location_ref"] = None
        self.node["physical_assets"] = []
        self.assertTrue(validate_passport(self.node)["digital_bound"])

    def test_immutable_schema_rejects_undeclared_fields(self):
        self.node["owner_is_genesis"] = True
        with self.assertRaisesRegex(PassportError, "INVALID_PASSPORT_SCHEMA"):
            validate_passport(self.node)

    def test_duplicate_references_rejected(self):
        self.node["physical_assets"] *= 2
        with self.assertRaisesRegex(PassportError, "DUPLICATE_REFERENCE"):
            validate_passport(self.node)


if __name__ == "__main__":
    unittest.main()
