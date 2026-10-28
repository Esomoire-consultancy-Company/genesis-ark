import unittest
import server


class PublicSiteTests(unittest.TestCase):
    def test_all_public_pages_render(self):
        for path in ["/", "/architecture", "/knowledge", "/evidence", "/status"]:
            status, mime, body = server.route(path)
            text = body.decode("utf-8")
            self.assertEqual(status, 200)
            self.assertTrue(mime.startswith("text/html"))
            self.assertIn("<main id=\"main\">", text)
            self.assertIn("PUBLIC PREVIEW", text)
            self.assertIn("noindex,nofollow", text)
            self.assertNotIn("%%", text)
            self.assertNotIn('href="http://postgres', text)

    def test_health_does_not_claim_api_access(self):
        code, mime, body = server.route("/healthz")
        self.assertEqual(code, 200)
        self.assertIn(b'"api_enabled": false', body)

    def test_robots_disallows_indexing(self):
        self.assertIn(b"Disallow: /", server.route("/robots.txt")[2])

    def test_unknown_route_fails_closed(self):
        for path in ["/v1/intents", "/secrets", "/.env", "/../../etc/passwd"]:
            self.assertEqual(server.route(path)[0], 404)

    def test_stylesheet_present(self):
        code, mime, body = server.route("/assets/site.css")
        self.assertEqual(code, 200)
        self.assertIn(b".site-header", body)


if __name__ == "__main__":
    unittest.main()
