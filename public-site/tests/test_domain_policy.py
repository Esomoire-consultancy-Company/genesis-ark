import unittest
from domain_policy import knowledge_landing_redirect, valid_dns_hostname


class DomainPolicyTests(unittest.TestCase):
    def test_valid_canonical_hostname(self):
        self.assertTrue(valid_dns_hostname("knowledge.synnergyz.com"))
        for value in ("", "localhost", "knowledge.synnergyz.com/other",
                      "https://knowledge.synnergyz.com", "KNOWLEDGE.synnergyz.com",
                      "knowledge..synnergyz.com", "knowledge.synnergyz.com@evil.example",
                      ".synnergyz.com", "knowledge.synnergyz.com:8080"):
            self.assertFalse(valid_dns_hostname(value), value)

    def test_owner_config_is_required(self):
        for configured in ("", "not-a-domain", "https://knowledge.synnergyz.com", None):
            self.assertIsNone(knowledge_landing_redirect("knowledge.synnergyz.com", "/", configured))

    def test_knowledge_host_home_redirect_is_exact_and_relative(self):
        h = "knowledge.synnergyz.com"
        self.assertEqual(knowledge_landing_redirect(h, "/", h), "/knowledge")
        self.assertEqual(knowledge_landing_redirect(h + ":8080", "/?a=1", h), "/knowledge")
        self.assertIsNone(knowledge_landing_redirect("evil-knowledge.synnergyz.com", "/", h))
        self.assertIsNone(knowledge_landing_redirect("knowledge.synnergyz.com.evil.example", "/", h))
        self.assertIsNone(knowledge_landing_redirect("genesis.synnergyz.com", "/", h))
        self.assertIsNone(knowledge_landing_redirect(h, "/architecture", h))
        self.assertIsNone(knowledge_landing_redirect(h, "/knowledge", h))
        self.assertIsNone(knowledge_landing_redirect(h, "/v1/intents", h))

    def test_invalid_port_and_host_do_not_redirect(self):
        for value in ("knowledge.synnergyz.com:foo", "knowledge.synnergyz.com:0",
                      "knowledge.synnergyz.com:99999", "[::1]", "evil.example:80",
                      "knowledge.synnergyz.com:443@attacker.com"):
            self.assertIsNone(knowledge_landing_redirect(value, "/", "knowledge.synnergyz.com"))
