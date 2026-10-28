"""Localhost-only HTTP simulator contract tests."""
import json
from pathlib import Path
import sys
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import HOST, make_server
from engine import SyntheticOracle, load_manifest


class SyntheticServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://{HOST}:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        # Test isolation: do not share replay state between test methods.
        self.server.RequestHandlerClass.oracle = SyntheticOracle(load_manifest())

    def call(self, method, route, payload=None, content_type="application/json"):
        raw = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base+route, data=raw, method=method,
                          headers={"Content-Type":content_type})
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def synthetic_request(self, **extra):
        return {"request_id":"SYN-REQ-SERVER-001", "actor_id":"SYN-ACTOR-CREATOR-01",
                "action":"creator.draft.synthetic", "environment":"synthetic-ci", **extra}

    def test_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_health_is_explicitly_non_executable(self):
        status, body = self.call("GET","/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["synthetic"])
        self.assertFalse(body["executable"])

    def test_actor_catalogue_contains_only_synthetic(self):
        status, body = self.call("GET","/catalog")
        self.assertEqual(status, 200)
        self.assertTrue(all(a["id"].startswith("SYN-") for a in body["actors"]))
        self.assertGreater(len(body["actors"]), 5)
        self.assertFalse(body["executable"])

    def test_simulation_produces_no_operational_authority(self):
        status, body = self.call("POST","/simulate",self.synthetic_request())
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "ALLOW")
        self.assertFalse(body["executable"])

    def test_duplicate_request_is_idempotent(self):
        a = self.call("POST","/simulate",self.synthetic_request())[1]
        b = self.call("POST","/simulate",self.synthetic_request())[1]
        self.assertEqual(a,b)

    def test_conflicting_replay_rejected(self):
        original_status, _ = self.call("POST", "/simulate", self.synthetic_request())
        self.assertEqual(original_status, 200)
        status, body = self.call("POST","/simulate",self.synthetic_request(
            action="node.service.promote.synthetic"))
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "INVALID_SYNTHETIC_REQUEST")

    def test_unrecognised_authority_field_rejected(self):
        status, body = self.call("POST","/simulate", self.synthetic_request(
            request_id="SYN-REQ-OTHER-001", decision="ALLOW"))
        self.assertEqual(status, 400)

    def test_non_json_rejected(self):
        status, body = self.call("POST","/simulate",self.synthetic_request(),"text/plain")
        self.assertEqual(status, 415)

    def test_unknown_path_has_no_side_effect(self):
        status, body = self.call("POST","/real/settle",self.synthetic_request())
        self.assertEqual(status, 404)

    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):
            make_server(-1)


if __name__ == "__main__":
    unittest.main()

# Extended fixture workbench contracts (never leave localhost).
class SyntheticWorkbenchHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://{HOST}:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, response.headers, response.read()

    def test_workbench_html_and_csp(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn(b"Synthetic Workbench", body)
        self.assertIn(b'tabindex="-1"', body)
        for anchor in (b'href="#explorer-title"', b'href="#simulation-title"', b'href="#receipt-title"'):
            self.assertIn(anchor, body)

    def test_workbench_assets_local_only(self):
        for path, media_type in (("/workbench.js", "text/javascript"),
                                 ("/workbench.css", "text/css")):
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertIn(media_type, headers["Content-Type"])
                self.assertGreater(len(body), 250)
        _, _, script = self.get("/workbench.js")
        self.assertNotIn(b"https://", script)
        self.assertNotIn(b"eval(", script)

    def test_catalog_contains_complete_synthetic_bindings(self):
        _, _, body = self.get("/catalog")
        catalog = json.loads(body)
        self.assertFalse(catalog["executable"])
        self.assertEqual(len(catalog["actors"]), 10)
        self.assertEqual(len(catalog["licences"]), 9)
        self.assertTrue(all(item["id"].startswith("SYN-LIC-") for item in catalog["licences"]))
        self.assertTrue(all(item["node_id"].startswith("SYN-") for item in catalog["representations"]))

    def test_workbench_exposes_expected_scenarios(self):
        _, _, body = self.get("/scenarios")
        catalog = json.loads(body)
        self.assertTrue(catalog["synthetic"])
        self.assertFalse(catalog["executable"])
        self.assertEqual(len(catalog["scenarios"]), 17)
        self.assertTrue(all(row["decision"] in ("ALLOW", "DENY", "ESCALATE")
                            for row in catalog["scenarios"]))

    def test_no_live_endpoint_or_path_traversal(self):
        for path in ("/api/identity", "/api/licences", "/../engine.py", "/production"):
            with self.subTest(path=path):
                try:
                    self.get(path)
                except HTTPError as error:
                    self.assertEqual(error.code, 404)
                else:
                    self.fail(f"unexpected endpoint exposed: {path}")
