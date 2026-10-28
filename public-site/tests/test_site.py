import http.client
import socket
import threading
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
        self.assertEqual(server.route("/robots.txt")[2], b"User-agent: *\nDisallow: /\n")

    def test_unknown_route_fails_closed(self):
        for path in ["/v1/intents", "/secrets", "/.env", "/../../etc/passwd"]:
            self.assertEqual(server.route(path)[0], 404)

    def test_stylesheet_present(self):
        code, mime, body = server.route("/assets/site.css")
        self.assertEqual(code, 200)
        self.assertIn(b".site-header", body)


class HTTPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.BoundedHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.worker = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.worker.join(timeout=3)

    def test_security_headers_and_head_over_real_http(self):
        for method in ("GET", "HEAD"):
            for path in ("/", "/healthz"):
                with self.subTest(method=method, path=path):
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", self.httpd.server_port, timeout=5
                    )
                    try:
                        connection.request(method, path)
                        response = connection.getresponse()
                        content = response.read()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(
                            response.getheader("X-Robots-Tag"),
                            "noindex, nofollow, noarchive",
                        )
                        self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
                        self.assertEqual(
                            response.getheader("X-Content-Type-Options"), "nosniff"
                        )
                        self.assertIn(
                            "default-src 'none'",
                            response.getheader("Content-Security-Policy", ""),
                        )
                        self.assertIn(
                            "frame-ancestors 'none'",
                            response.getheader("Content-Security-Policy", ""),
                        )
                        self.assertNotIn("Python", response.getheader("Server", ""))
                        self.assertGreater(int(response.getheader("Content-Length")), 0)
                        if method == "HEAD":
                            self.assertEqual(content, b"")
                        else:
                            self.assertTrue(content)
                    finally:
                        connection.close()

    def test_malformed_absolute_request_gets_400(self):
        self.assertEqual(server.route("http://[::1")[0], 400)
        with socket.create_connection(
            ("127.0.0.1", self.httpd.server_port), timeout=5
        ) as connection:
            connection.sendall(
                b"GET http://[::1 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            )
            self.assertTrue(connection.recv(128).startswith(b"HTTP/1.0 400"))

    def test_listener_has_finite_limits(self):
        self.assertEqual(server.Handler.timeout, 10)
        self.assertEqual(self.httpd.max_connections, 32)


if __name__ == "__main__":
    unittest.main()
