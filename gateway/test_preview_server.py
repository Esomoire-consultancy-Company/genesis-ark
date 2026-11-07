"""Bounded local-loopback tests for Genesis ARK's static preview adapter."""
from __future__ import annotations

from contextlib import redirect_stderr
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from threading import Thread
from unittest import TestCase
from unittest.mock import patch

from preview_server import ASSETS, StaticPreviewHandler, main, preview_opted_in

ROOT = Path(__file__).resolve().parent


class PreviewServerTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StaticPreviewHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def request(self, method: str, resource: str):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, resource)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_health_is_explicitly_preview_only(self):
        status, headers, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"healthy:static-preview-only\n")
        self.assertEqual(headers["X-Genesis-Deployment-Qualification"], "PREVIEW_NOT_ACCEPTED")

    def test_home_is_actual_static_index(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(body, (ROOT / "index.html").read_bytes())

    def test_all_assets_exactly_allowlisted(self):
        self.assertEqual(set(ASSETS), {"/", "/index.html", "/styles.css", "/portal.js", "/favicon.svg"})
        for resource, (filename, _) in ASSETS.items():
            with self.subTest(resource=resource):
                status, headers, body = self.request("GET", resource)
                self.assertEqual(status, 200)
                self.assertEqual(body, (ROOT / filename).read_bytes())
                self.assertEqual(headers["Content-Length"], str(len(body)))

    def test_head_never_emits_body(self):
        status, headers, body = self.request("HEAD", "/portal.js")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Length"], str((ROOT / "portal.js").stat().st_size))

    def test_no_runtime_code_is_served(self):
        for resource in ("/preview_server.py", "/test_preview_server.py", "/check.py",
                         "/Dockerfile.preview", "/.dockerignore", "/.git/HEAD",
                         "/control-plane/README.md", "/registry/cloud-services.json",
                         "/gateway/../control-plane/README.md"):
            with self.subTest(resource=resource):
                status, _, body = self.request("GET", resource)
                self.assertEqual(status, 404)
                self.assertEqual(body, b"NOT_FOUND\n")

    def test_encoded_traversal_is_not_served(self):
        for resource in ("/%2e%2e/README.md", "/..%2fcontrol-plane%2fREADME.md",
                         "/%2fetc%2fpasswd", "/gateway%2fpreview_server.py"):
            with self.subTest(resource=resource):
                status, _, body = self.request("GET", resource)
                self.assertEqual(status, 404)
                self.assertEqual(body, b"NOT_FOUND\n")

    def test_unrecognized_url_is_not_index_fallback(self):
        status, _, body = self.request("GET", "/api/warden/execute")
        self.assertEqual(status, 404)
        self.assertEqual(body, b"NOT_FOUND\n")

    def test_no_post_endpoint(self):
        status, _, _ = self.request("POST", "/")
        self.assertEqual(status, 501)

    def test_all_static_responses_disallow_caching_and_frames(self):
        for resource in ("/", "/healthz", "/missing", "/portal.js"):
            status, headers, _ = self.request("GET", resource)
            self.assertIn(status, (200, 404))
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(headers.get("X-Frame-Options"), "DENY")
            self.assertIn("connect-src 'none'", headers.get("Content-Security-Policy", ""))
            self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))

    def test_no_default_opt_in(self):
        self.assertFalse(preview_opted_in({}))
        self.assertFalse(preview_opted_in({"GENESIS_STATIC_PREVIEW_ENABLE": "false"}))
        self.assertFalse(preview_opted_in({"GENESIS_STATIC_PREVIEW_ENABLE": "TRUE"}))
        self.assertTrue(preview_opted_in({"GENESIS_STATIC_PREVIEW_ENABLE": "true"}))

    def test_start_rejected_without_explicit_opt_in(self):
        with patch.dict("os.environ", {"GENESIS_STATIC_PREVIEW_ENABLE": "false"}):
            with redirect_stderr(StringIO()) as err:
                self.assertEqual(main(), 78)
            self.assertIn("HOLD:", err.getvalue())

    def test_bad_port_rejected_before_listener(self):
        for value in ("0", "80", "abc", "-1", "65536"):
            with self.subTest(port=value):
                with patch.dict("os.environ",
                                {"GENESIS_STATIC_PREVIEW_ENABLE": "true", "PORT": value}):
                    with redirect_stderr(StringIO()):
                        self.assertEqual(main(), 78)

    def test_container_is_nonroot_and_copies_only_five_files(self):
        dockerfile = (ROOT / "Dockerfile.preview").read_text()
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("GENESIS_STATIC_PREVIEW_ENABLE", dockerfile)
        self.assertNotIn("ENV GENESIS_STATIC_PREVIEW_ENABLE=true", dockerfile)
        copy_lines = [s.strip() for s in dockerfile.splitlines() if s.startswith("COPY ")]
        self.assertEqual(len(copy_lines), 1)
        self.assertIn("index.html styles.css portal.js favicon.svg preview_server.py ./",
                      copy_lines[0])
        self.assertNotIn("COPY .", copy_lines[0])

    def test_gateway_build_context_excludes_control_plane(self):
        ignore = (ROOT / ".dockerignore").read_text()
        self.assertEqual(ignore.splitlines()[1], "*")
        self.assertNotIn("!control-plane", ignore)
        self.assertIn("!index.html", ignore)
