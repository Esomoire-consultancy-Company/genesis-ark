"""R0.6 in-process API and two-administrator review tests. No live server."""
import json
import sqlite3
from datetime import timedelta

import pytest

from genesis_control_plane.work_api import ApiRequest, WorkStagingAPI
from genesis_control_plane.work_gateway import AdmissionDenied
from genesis_control_plane.work_notice import NOTICE_VERSION, WorkNoticeConsent
from genesis_control_plane.work_r05 import WorkEvidenceStaging
from genesis_control_plane.work_review import WardenReviewQueue

from test_work_identity_r04 import NOW, SOURCE_KEY, env, mint, packet

ORIGIN = "https://staging.example.invalid"


@pytest.fixture
def api(env):
    stage = WorkEvidenceStaging(
        db_path=env["tmp_path"] / "stage.sqlite",
        river_path=env["tmp_path"] / "river.jsonl",
        verifier=env["verifier"], warden_store=env["store"],
        source_key_resolver=lambda tenant, source:
            SOURCE_KEY if (tenant, source) == ("BNR-T1", "APP-01") else None,
    )
    notices = WorkNoticeConsent(stage)
    review = WardenReviewQueue(env["tmp_path"] / "review.sqlite",
                               verifier=env["verifier"], registry=env["store"])
    return WorkStagingAPI(staging=stage, notices=notices,
                          reviews=review, allowed_origins=frozenset({ORIGIN}))


def call(api, *, method, path, token=None, data=None, origin=ORIGIN,
         headers=None, body=None):
    hdrs = {"origin": origin}
    if token:
        hdrs["authorization"] = "Bearer " + token
    if method == "POST":
        hdrs["content-type"] = "application/json"
    if headers:
        hdrs.update(headers)
    if body is None:
        body = json.dumps(data if data is not None else {}, separators=(",", ":")).encode() if method == "POST" else b""
    return api.handle(ApiRequest(method=method, path=path, headers=hdrs, body=body), now=NOW)


def test_notice_public_and_versioned(api):
    res = call(api, method="GET", path="/v1/work/notice")
    assert res.status == 200
    assert res.body["version"] == NOTICE_VERSION
    assert "No raw" not in res.body["text"] or "Raw prompts" in res.body["text"]
    assert res.headers["Cache-Control"] == "no-store"


def test_member_must_affirm_correct_notice(api, env):
    token = mint(env, scopes="work:consent work:read work:capture")
    data = dict(work_id="GW-001", expires_at=(NOW+timedelta(days=2)).isoformat(),
                notice_version=NOTICE_VERSION, affirmative=False)
    for version, agreed in [(NOTICE_VERSION, False), ("UNKNOWN", True)]:
        result = call(api, method="POST", path="/v1/work/consent", token=token,
                      data={**data, "notice_version": version, "affirmative": agreed})
        assert result.status == 403 and result.body["error"] == "R06_NOTICE_ACCEPTANCE_REQUIRED"
    assert sqlite3.connect(api.staging.db_path).execute(
        "SELECT count(*) FROM subject_consent").fetchone()[0] == 0
    result = call(api, method="POST", path="/v1/work/consent", token=token,
                  data={**data, "affirmative": True})
    assert result.status == 201 and result.body["notice_version"] == NOTICE_VERSION
    with sqlite3.connect(api.staging.db_path) as db:
        assert db.execute("SELECT count(*) FROM subject_consent").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM notice_acceptance").fetchone()[0] == 1
    result = call(api, method="POST", path="/v1/work/withdraw", token=token,
                  data={"work_id":"GW-001"})
    assert result.status == 200 and result.body["status"] == "withdrawn"


def test_two_independent_admins_required_to_register_grant(api, env):
    proposer = mint(env, sub="DM-ADMIN-A", scopes="work:admin", jti="PROPOSER")
    approver = mint(env, sub="DM-ADMIN-B", scopes="work:admin work:approve", jti="APPROVER")
    requested = {
        "target_id": "DM-001", "source": "APP-01", "work_id": "GW-001",
        "channels": ["typed", "voice_dictation"], "kinds": ["work.input"],
        "expires_at": (NOW+timedelta(days=4)).isoformat(),
    }
    create = call(api, method="POST", path="/v1/admin/reviews",
                  token=proposer, data=requested)
    assert create.status == 202
    proposal = create.body["proposal_id"]
    with pytest.raises(AdmissionDenied, match="SOURCE_NOT_REGISTERED"):
        actor = env["verifier"].verify(mint(env), required_scope="work:capture", now=NOW)
        api.staging.warden_store.resolve(actor, work_id="GW-001", now=NOW)
    single = call(api, method="POST", path=f"/v1/admin/reviews/{proposal}/approve",
                  token=mint(env, sub="DM-ADMIN-A",
                             scopes="work:admin work:approve", jti="PROPOSER-2"), data={})
    assert single.status == 403 and single.body["error"] == "R06_INDEPENDENT_APPROVER_REQUIRED"
    member = call(api, method="POST", path=f"/v1/admin/reviews/{proposal}/approve",
                  token=mint(env, sub="DM-001", scopes="work:admin work:approve", jti="MEMBER"), data={})
    assert member.status == 403 and member.body["error"] == "R06_INDEPENDENT_APPROVER_REQUIRED"
    approved = call(api, method="POST", path=f"/v1/admin/reviews/{proposal}/approve",
                    token=approver, data={})
    assert approved.status == 200 and approved.body["status"] == "approved"
    duplicate = call(api, method="POST", path=f"/v1/admin/reviews/{proposal}/approve",
                     token=approver, data={})
    assert duplicate.status == 403 and duplicate.body["error"] == "R06_PROPOSAL_NOT_PENDING"


def test_api_capture_and_progress_cannot_precede_consent_and_grant(api, env):
    member = mint(env, scopes="work:consent work:read work:capture")
    pending = call(api, method="POST", path="/v1/work/capture",
                   token=member, data={"packet": packet()})
    assert pending.status == 403
    # Consent alone does not bypass a missing independent grant.
    notice = call(api, method="POST", path="/v1/work/consent", token=member, data={
        "work_id":"GW-001", "expires_at":(NOW+timedelta(days=2)).isoformat(),
        "notice_version":NOTICE_VERSION, "affirmative":True,
    })
    assert notice.status == 201
    denied = call(api, method="POST", path="/v1/work/capture",
                  token=member, data={"packet":packet()})
    assert denied.status == 403
    request = call(api, method="POST", path="/v1/admin/reviews",
                   token=mint(env,sub="DM-A",scopes="work:admin",jti="J-A"), data={
                       "target_id":"DM-001", "source":"APP-01", "work_id":"GW-001",
                       "channels":["voice_dictation"], "kinds":["work.input"],
                       "expires_at":(NOW+timedelta(days=4)).isoformat()})
    assert request.status == 202
    ready = call(api, method="POST",
                 path=f"/v1/admin/reviews/{request.body['proposal_id']}/approve",
                 token=mint(env,sub="DM-B",scopes="work:admin work:approve",jti="J-B"),
                 data={})
    assert ready.status == 200
    queued = call(api, method="POST", path="/v1/work/capture",
                  token=member, data={"packet":packet()})
    assert queued.status == 202 and queued.body["status"] == "pending"
    progress = call(api, method="GET", path="/v1/work/GW-001/progress", token=member)
    assert progress.status == 200
    assert progress.body["pending"] == 1 and progress.body["input_messages"] == 0
    # Drain is NOT exposed as a public API route. An operator-only consumer
    # must do it independently.
    assert call(api,method="POST",path="/v1/work/drain",token=member,data={}).status == 404
    assert api.staging.drain(now=NOW)["projected"] == 1
    progress = call(api,method="GET",path="/v1/work/GW-001/progress",token=member)
    assert progress.body["input_messages"] == 1 and progress.body["pending"] == 0


def test_api_origin_cookie_content_type_and_json_restrictions(api, env):
    token = mint(env, scopes="work:consent")
    for kwargs in [
        {"origin":"https://evil.invalid"},
        {"headers":{"cookie":"session=secret"}},
        {"headers":{"content-type":"text/plain"}},
        {"body":b'{"work_id":"one","work_id":"two"}'},
        {"body":b"x" * 17000},
    ]:
        res = call(api,method="POST",path="/v1/work/withdraw",
                   token=token,data={"work_id":"GW-001"},**kwargs)
        assert res.status == 403
    no_token = call(api,method="GET",path="/v1/work/GW-001/progress")
    assert no_token.status == 403 and no_token.body["error"] == "R06_BEARER_REQUIRED"
    no_leak = call(api,method="GET",path="/v1/work/GW-001/progress",
                   token="an-invalid-token")
    assert no_leak.status == 401
    assert "an-invalid-token" not in json.dumps(no_leak.body)


def test_api_read_is_tenant_scoped(api, env):
    member = mint(env,scopes="work:consent work:capture work:read")
    call(api, method="POST",path="/v1/work/consent",token=member,
         data={"work_id":"GW-001","expires_at":(NOW+timedelta(days=2)).isoformat(),
               "notice_version":NOTICE_VERSION,"affirmative":True})
    own = call(api,method="GET",path="/v1/work/GW-001/progress",token=member)
    other = call(api,method="GET",path="/v1/work/GW-001/progress",
                 token=mint(env,tenant="BNR-T2",jti="J-OTHER",scopes="work:read"))
    assert own.status == other.status == 200
    assert own.body["tenant_id"] == "BNR-T1"
    assert other.body["tenant_id"] == "BNR-T2"
    assert other.body["accepted"] == 0


def test_admin_proposal_scope_denied_if_not_admin_or_other_tenant(api,env):
    proposal = {
        "target_id":"DM-001","source":"APP-01","work_id":"GW-001",
        "channels":["typed"],"kinds":["work.input"],
        "expires_at":(NOW+timedelta(days=3)).isoformat(),
    }
    nope = call(api,method="POST",path="/v1/admin/reviews",
                token=mint(env,scopes="work:read"),data=proposal)
    assert nope.status == 401
    create = call(api,method="POST",path="/v1/admin/reviews",
                  token=mint(env,sub="DM-ADMIN-A",scopes="work:admin",jti="J-A"),data=proposal)
    assert create.status == 202
    hidden = call(api,method="GET",path=f"/v1/admin/reviews/{create.body['proposal_id']}",
                  token=mint(env,tenant="BNR-T2",sub="DM-ADMIN-OTHER",
                             scopes="work:admin",jti="J-B"))
    assert hidden.status == 403 and hidden.body["error"] == "R06_PROPOSAL_NOT_VISIBLE"
