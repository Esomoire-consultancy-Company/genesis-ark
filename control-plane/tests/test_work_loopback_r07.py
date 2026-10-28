"""Synthetic real-loopback R0.7 end-to-end staging acceptance tests.

No Docker, external identity provider, real user data, or public listening
address. All bearer tokens are created with an ephemeral in-test RSA key.
"""
from __future__ import annotations

import http.client
import io
import json
import threading
from datetime import timedelta
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

from genesis_control_plane.work_api import WorkStagingAPI
from genesis_control_plane.work_gateway import AdmissionDenied
from genesis_control_plane.work_loopback import WorkLoopbackWSGI
from genesis_control_plane.work_notice import NOTICE_VERSION, WorkNoticeConsent
from genesis_control_plane.work_r05 import WorkEvidenceStaging
from genesis_control_plane.work_review import WardenReviewQueue
from test_work_identity_r04 import NOW, SOURCE_KEY, env, mint, packet

ORIGIN = "https://staging.example.invalid"


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Never write Authorization headers, packet data or test output.
        pass


@pytest.fixture
def live(env):
    stage = WorkEvidenceStaging(
        db_path=env["tmp_path"] / "e2e-stage.sqlite",
        river_path=env["tmp_path"] / "e2e-river.jsonl",
        verifier=env["verifier"], warden_store=env["store"],
        source_key_resolver=lambda tenant, source:
            SOURCE_KEY if (tenant, source) == ("BNR-T1", "APP-01") else None,
    )
    api = WorkStagingAPI(
        staging=stage, notices=WorkNoticeConsent(stage),
        reviews=WardenReviewQueue(env["tmp_path"] / "e2e-reviews.sqlite",
                                  verifier=env["verifier"],
                                  registry=env["store"]),
        allowed_origins=frozenset({ORIGIN}),
    )
    transport = WorkLoopbackWSGI(api, clock=lambda: NOW)
    server = make_server("127.0.0.1", 0, transport, handler_class=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield (server.server_port, stage, api)
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def call(port, method, path, *, token=None, data=None,
         origin=ORIGIN, extra=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Origin": origin}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
    else:
        body = None
    headers.update(extra or {})
    try:
        connection.request(method, path, body=body, headers=headers)
        result = connection.getresponse()
        response = json.loads(result.read())
        assert result.getheader("Cache-Control") == "no-store"
        assert result.getheader("X-Content-Type-Options") == "nosniff"
        return result.status, response
    finally:
        connection.close()


def test_real_loopback_full_flow_and_private_dashboard(live, env):
    port, stage, _ = live
    member = mint(env, scopes="work:consent work:capture work:read", jti="MEMBER")
    proposer = mint(env, sub="DM-ADMIN-A", scopes="work:admin", jti="PROPOSER")
    approver = mint(env, sub="DM-ADMIN-B",
                    scopes="work:admin work:approve", jti="APPROVER")
    foreign = mint(env, tenant="BNR-T2", jti="FOREIGN", scopes="work:read")

    status, notice = call(port, "GET", "/v1/work/notice")
    assert status == 200 and notice["version"] == NOTICE_VERSION

    status, before = call(port, "POST", "/v1/work/capture",
                          token=member, data={"packet": packet()})
    assert status == 403 and before["error"] == "WARDEN_SOURCE_NOT_REGISTERED"

    expiry = (NOW + timedelta(days=2)).isoformat()
    status, proposal = call(port, "POST", "/v1/admin/reviews",
                            token=proposer, data={
                                "target_id": "DM-001", "source": "APP-01",
                                "work_id": "GW-001", "channels": ["voice_dictation"],
                                "kinds": ["work.input"],
                                "expires_at": expiry,
                            })
    assert status == 202 and proposal["status"] == "pending"
    review_path = "/v1/admin/reviews/" + proposal["proposal_id"] + "/approve"

    status, denial = call(port, "POST", review_path,
                          token=mint(env, sub="DM-ADMIN-A",
                                     scopes="work:admin work:approve", jti="SELF"),
                          data={})
    assert status == 403 and denial["error"] == "R06_INDEPENDENT_APPROVER_REQUIRED"
    status, approved = call(port, "POST", review_path, token=approver, data={})
    assert status == 200 and approved["status"] == "approved"

    status, denied = call(port, "POST", "/v1/work/capture",
                          token=member, data={"packet": packet()})
    assert status == 403 and denied["error"] == "R05_SUBJECT_CONSENT_REQUIRED"

    status, declined = call(port, "POST", "/v1/work/consent",
                            token=member, data={
                                "work_id": "GW-001", "expires_at": expiry,
                                "notice_version": NOTICE_VERSION, "affirmative": False,
                            })
    assert status == 403 and declined["error"] == "R06_NOTICE_ACCEPTANCE_REQUIRED"
    status, consent = call(port, "POST", "/v1/work/consent",
                           token=member, data={
                               "work_id": "GW-001", "expires_at": expiry,
                               "notice_version": NOTICE_VERSION, "affirmative": True,
                           })
    assert status == 201 and consent["status"] == "opted_in"
    assert consent["notice_receipt_id"]

    status, pending = call(port, "POST", "/v1/work/capture",
                           token=member, data={"packet": packet()})
    assert status == 202 and pending["status"] == "pending"
    assert not stage.river_path.exists()

    status, counts = call(port, "GET", "/v1/work/GW-001/progress", token=member)
    assert status == 200
    assert counts["pending"] == 1 and counts["input_messages"] == 0
    assert counts["submitted_input_messages"] == 1

    assert stage.drain(now=NOW) == {"projected": 1, "blocked": 0}
    status, counts = call(port, "GET", "/v1/work/GW-001/progress", token=member)
    assert status == 200 and counts["projected"] == 1
    assert counts["channels"] == {"voice_dictation": 1}
    assert counts["attachments"]["image"] == 1
    assert counts["verified_execution_count"] is None
    assert counts["finalized_count"] is None
    assert stage.reconcile()["consistent"]

    status, duplicate = call(port, "POST", "/v1/work/capture",
                             token=member, data={"packet": packet()})
    assert status == 202 and duplicate["duplicate"] is True
    assert duplicate["status"] == "projected"

    status, outsider = call(port, "GET", "/v1/work/GW-001/progress",
                            token=foreign)
    assert status == 200 and outsider["accepted"] == 0
    assert outsider["tenant_id"] == "BNR-T2"

    status, withdrawn = call(port, "POST", "/v1/work/withdraw",
                             token=member, data={"work_id": "GW-001"})
    assert status == 200 and withdrawn["status"] == "withdrawn"
    status, denied = call(port, "POST", "/v1/work/capture",
                          token=member,
                          data={"packet": packet(message="MSG-02", capture="CAP-02")})
    assert status == 403 and denied["error"] == "R05_SUBJECT_CONSENT_REQUIRED"

    # Previously projected evidence remains visible and never counts as
    # verified/finalized merely because consent has been withdrawn.
    status, counts = call(port, "GET", "/v1/work/GW-001/progress", token=member)
    assert status == 200 and counts["projected"] == 1


def test_real_loopback_rejects_hostile_origin_and_cookies(live, env):
    port, _, _ = live
    member = mint(env, scopes="work:read")
    status, result = call(port, "GET", "/v1/work/GW-001/progress",
                          token=member, origin="https://outside.invalid")
    assert status == 403 and result["error"] == "R06_ORIGIN_DENIED"
    status, result = call(port, "GET", "/v1/work/GW-001/progress",
                          token=member, extra={"Cookie": "session=untrusted"})
    assert status == 403 and result["error"] == "R06_COOKIES_DENIED"
    status, result = call(port, "GET", "/v1/work/GW-001/progress",
                          token="bad.token.value")
    assert status == 401 and result["error"] == "R06_IDENTITY_DENIED"
    assert "bad.token.value" not in json.dumps(result)


def test_transport_rejects_remote_clients_and_host_spoof(live):
    port, _, api = live
    response = {}
    def start(status, headers):
        response["status"] = status
    wsgi = WorkLoopbackWSGI(api, clock=lambda: NOW)
    for address, host in [("203.0.113.1", "127.0.0.1"), ("127.0.0.1", "attacker.invalid")]:
        envelope = {"REMOTE_ADDR": address, "HTTP_HOST": host,
                    "wsgi.url_scheme": "http", "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/v1/work/notice", "CONTENT_LENGTH": "",
                    "wsgi.input": io.BytesIO(b"")}
        result = b"".join(wsgi(envelope, start))
        assert response["status"].startswith("403")
        assert json.loads(result)["error"] == "R07_LOOPBACK_ONLY"


def test_no_public_projection_or_admin_override_endpoints(live, env):
    port, _, _ = live
    admin = mint(env, sub="DM-ADMIN-A",
                 scopes="work:admin work:approve", jti="ADMIN")
    for route in ("/v1/work/drain", "/v1/admin/direct-grant", "/v1/river/raw"):
        status, result = call(port, "POST", route, token=admin, data={})
        assert status == 404 and result["error"] == "R06_ROUTE_NOT_FOUND"


def test_large_request_denied_before_json_body_parsing(live, env):
    port, _, _ = live
    token = mint(env, scopes="work:capture")
    status, result = call(port, "POST", "/v1/work/capture",
                          token=token, data={"packet": {"raw_text": "X" * 18000}})
    assert status == 413 and result["error"] == "R07_PAYLOAD_TOO_LARGE"
