"""Regression checks for the dual-track Genesis ARK staging decision.

Checks the recorded architecture boundary; does not call cloud accounts or
interpret an evidence document as deployment authorization.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "staging-dual-track.r01.json"


class DualTrackAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_both_tracks_are_explicit_and_distinct(self):
        self.assertEqual(self.record["decision"], "BOTH_TRACKS_SELECTED_FOR_CONTROLLED_ENGINEERING_REVIEW")
        self.assertEqual(self.record["existing_staging"]["track"], "A_REUSE")
        self.assertEqual(self.record["new_static_target"]["track"], "B_INDEPENDENT")

    def test_existing_staging_environment_identity(self):
        live = self.record["existing_staging"]
        self.assertEqual(live["project_name"], "genesis-ark-gateway-staging")
        self.assertEqual(live["environment"], "staging")
        self.assertEqual(len(live["observed_services"]), 4)
        self.assertFalse(live["provider_settings_changed"])
        self.assertFalse(live["automatic_rollout"])

    def test_two_public_previews_proven_by_read_only_browser(self):
        live = self.record["existing_staging"]
        http = live["http_verification"]
        self.assertEqual(http["method"], "READ_ONLY_PUBLIC_CLOUD_BROWSER")
        self.assertEqual(http["scope"], "PUBLIC_LANDING_PAGE_ONLY")
        for key in ("living_gateway", "public_site"):
            self.assertEqual(http[key]["http_status"], 200)
            self.assertFalse(http[key]["login_required"])
            self.assertTrue(http[key]["url"].startswith("https://"))
            self.assertTrue(http[key]["title"])
        self.assertFalse(http["cross_host_authorization_verified"])

    def test_private_cloud_gateway_and_postgres_never_public(self):
        services = self.record["existing_staging"]["observed_services"]
        for service in services:
            if service["name"] in ("genesis-cloud-gateway-r01", "Postgres"):
                self.assertIsNone(service["public_domain"])
        self.assertFalse(self.record["existing_staging"]["privileged_gateway_interface_allowed"])
        self.assertFalse(self.record["existing_staging"]["static_preview_customer_data_allowed"])

    def test_new_track_remains_unprovisioned_and_default_off(self):
        future = self.record["new_static_target"]
        self.assertEqual(future["default_start"], "HOLD_EXIT_78")
        self.assertEqual(future["required_opt_in"], "GENESIS_STATIC_PREVIEW_ENABLE=true")
        for key in ("environment_exists", "provisioned", "deployed", "dns_or_domain_changed"):
            self.assertFalse(future[key], key)
        for key in ("registry_access", "warden_capability", "river_connection", "commercial_rights"):
            self.assertFalse(future[key], key)

    def test_separate_target_requires_financial_authority(self):
        future = self.record["new_static_target"]
        cost = self.record["cost_control"]
        self.assertEqual(future["staging_acceptance_plan"]["provisioning_decision"], "NOT_YET_AUTHORIZED")
        self.assertEqual(future["staging_acceptance_plan"]["provider_target_status"], "NOT_CREATED")
        self.assertEqual(future["staging_acceptance_plan"]["financial_cap"], "NOT_APPROVED")
        self.assertEqual(cost["new_service_cost"], "NOT_QUOTED")
        self.assertEqual(cost["creation_approval"], "REQUIRED")
        self.assertTrue(cost["no_duplicate_gateway_or_postgres"])

    def test_document_cannot_grant_release(self):
        self.assertEqual(self.record["release_gate"], "HOLD")
        self.assertEqual(self.record["staging_decision"], "REVIEW_ONLY_NOT_PRODUCTION")
        self.assertFalse(self.record["human_release_authorization"])


if __name__ == "__main__":
    unittest.main()
