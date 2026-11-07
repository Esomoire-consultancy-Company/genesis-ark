"""Read-only dual-track staging contract checks; never contact provider APIs."""
import json
from pathlib import Path
import unittest


MANIFEST = Path(__file__).with_name("staging-dual-track.r01.json")


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class DualTrackAdmissionTests(unittest.TestCase):
    def test_tracks_have_separate_roles(self):
        m = load()
        self.assertEqual(m["existing_staging"]["track"], "A_REUSE")
        self.assertEqual(m["new_static_target"]["track"], "B_INDEPENDENT")

    def test_admission_remains_hold(self):
        m = load()
        self.assertEqual(m["release_gate"], "HOLD")
        self.assertFalse(m["human_release_authorization"])

    def test_existing_services_present_and_unmodified(self):
        m = load()
        a = m["existing_staging"]
        self.assertFalse(a["provider_settings_changed"])
        self.assertEqual(len(a["observed_services"]), 4)
        self.assertEqual(sum(s["state"] == "online" for s in a["observed_services"]), 4)

    def test_only_two_services_have_public_domains(self):
        services = load()["existing_staging"]["observed_services"]
        public = [s for s in services if s["public_domain"]]
        self.assertEqual(len(public), 2)
        self.assertTrue(all(s["name"] != "genesis-cloud-gateway-r01" for s in public))
        self.assertTrue(all("Postgres" != s["name"] for s in public))

    def test_external_http_check_does_not_claim_authority(self):
        check = load()["existing_staging"]["http_verification"]
        self.assertEqual(check["scope"], "PUBLIC_LANDING_PAGE_ONLY")
        self.assertFalse(check["private_gateway_or_database_inspected"])
        self.assertFalse(check["cross_host_authorization_verified"])
        self.assertEqual(check["living_gateway"]["http_status"], 200)
        self.assertEqual(check["public_site"]["http_status"], 200)

    def test_existing_preview_domains_are_distinct(self):
        check = load()["existing_staging"]["http_verification"]
        urls = [check["living_gateway"]["url"], check["public_site"]["url"]]
        self.assertEqual(len(set(urls)), 2)
        self.assertTrue(all(u.startswith("https://") and u.endswith(".up.railway.app/") for u in urls))

    def test_existing_private_services_not_exposed(self):
        m = load()
        self.assertFalse(m["existing_staging"]["privileged_gateway_interface_allowed"])
        self.assertFalse(m["existing_staging"]["static_preview_customer_data_allowed"])

    def test_new_target_not_created_or_deployed(self):
        b = load()["new_static_target"]
        self.assertFalse(b["environment_exists"])
        self.assertFalse(b["provisioned"])
        self.assertFalse(b["deployed"])
        self.assertFalse(b["dns_or_domain_changed"])
        self.assertEqual(b["staging_acceptance_plan"]["provider_target_status"], "NOT_CREATED")

    def test_new_target_opt_in_required(self):
        b = load()["new_static_target"]
        self.assertEqual(b["required_opt_in"], "GENESIS_STATIC_PREVIEW_ENABLE=true")
        self.assertEqual(b["default_start"], "HOLD_EXIT_78")

    def test_new_preview_has_no_private_authority(self):
        b = load()["new_static_target"]
        for name in ("registry_access", "warden_capability", "river_connection", "commercial_rights"):
            self.assertFalse(b[name], name)

    def test_cost_cap_and_owner_approval_are_not_fabricated(self):
        m = load()
        self.assertEqual(m["cost_control"]["new_service_cost"], "NOT_QUOTED")
        self.assertEqual(m["cost_control"]["creation_approval"], "REQUIRED")
        self.assertEqual(m["new_static_target"]["staging_acceptance_plan"]["financial_cap"], "NOT_APPROVED")
        self.assertEqual(m["new_static_target"]["staging_acceptance_plan"]["provisioning_decision"], "NOT_YET_AUTHORIZED")

    def test_does_not_replace_running_service(self):
        m = load()
        self.assertTrue(m["cost_control"]["existing_stage_keep_unmodified"])
        self.assertTrue(m["cost_control"]["no_duplicate_gateway_or_postgres"])
        self.assertFalse(m["existing_staging"]["automatic_rollout"])
