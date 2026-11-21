"""Run: python3 -m unittest discover -s knowledge-roads -p 'test_*.py' -v"""
import unittest
from navigation import assess_navigation, public_catalogue

class PublicBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"frameworks": [
            {"id": "FOR-0002", "name": "Bayes' theorem", "roles": ["road", "engine"],
             "visibility": "public", "registered": False, "secret": "must-not-leak"},
            {"id": "PRIVATE", "name": "Private methodology", "roles": ["road"],
             "visibility": "restricted", "registered": False},
            {"id": "LIVE", "name": "Production component", "roles": ["engine"],
             "visibility": "public", "registered": True},
        ]}

    def test_public_metadata_allowlist(self):
        result = public_catalogue(self.data)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["frameworks"][0]["id"], "FOR-0002")
        self.assertNotIn("secret", str(result))
        self.assertFalse(result["frameworks"][0]["execution_allowed"])

    def test_search_is_readonly(self):
        self.assertEqual(public_catalogue(self.data, "bayes")["count"], 1)
        self.assertEqual(public_catalogue(self.data, "private")["count"], 0)

    def test_public_browse_is_not_warden_permit(self):
        decision = assess_navigation({"action": "browse.public"})
        self.assertEqual(decision.disposition, "PUBLIC_PREVIEW")
        self.assertFalse(decision.real_authority)
        self.assertFalse(decision.execution_allowed)

    def test_public_browse_cannot_leak_resource(self):
        self.assertEqual(assess_navigation({"action": "browse.public", "resource_id": "X"}).disposition, "DENY")

    def test_nav_stays_on_hold_even_with_client_permit_flag(self):
        decision = assess_navigation({"action": "navigate.readonly", "warden_permit": True,
                                      "registered": True, "identity_verified": True})
        self.assertEqual(decision.disposition, "HOLD")
        self.assertFalse(decision.real_authority)

    def test_navigate_mutation_is_denied(self):
        self.assertEqual(assess_navigation({"action": "navigate.readonly", "execute": True}).disposition, "DENY")

    def test_other_warden_capability_not_reused(self):
        self.assertEqual(assess_navigation({"action": "container.instance.restart"}).disposition, "DENY")

    def test_unknown_action_denied(self):
        self.assertEqual(assess_navigation({}).disposition, "DENY")

if __name__ == "__main__":
    unittest.main()
