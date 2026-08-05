from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cloudbrowser_service.errors import ForbiddenError, StateConflictError
from cloudbrowser_service.executor import PlaywrightChromiumExecutor
from cloudbrowser_service.models import (
    BrowserActionRequest,
    BrowserActionType,
    BrowserPolicy,
    BrowserSession,
    SessionStatus,
)

CHROMIUM = Path("/usr/bin/chromium")
pytestmark = pytest.mark.skipif(not CHROMIUM.exists(), reason="system Chromium unavailable")
BASE_URL = "https://allowed.test"


def fixture_route(url: str, headers: dict[str, str]):
    if url.endswith("/set-cookie"):
        return 200, {"content-type": "text/html", "set-cookie": "actor_box=private; Path=/"}, b"cookie set"
    if url.endswith("/echo-cookie"):
        return 200, {"content-type": "text/html"}, headers.get("cookie", "NONE").encode()
    return 200, {"content-type": "text/html"}, b"<title>Genesis Test</title><body>ready</body>"


def session(identifier: str) -> BrowserSession:
    now = datetime.now(timezone.utc)
    return BrowserSession(
        browser_session_id=f"BROWSER-SESSION-{identifier}",
        box_id="BOX-TEST-001",
        digitalme_id="DIGITALME-TEST-001",
        runtime_id="RUNTIME-TEST-001",
        context_id="CONTEXT-TEST-001",
        workspace_id="WORKSPACE-TEST-001",
        policy_id="POLICY-TEST-001",
        policy_decision_id="DECISION-TEST-001",
        capability_id=f"CAPABILITY-{identifier}",
        session_status=SessionStatus.ACTIVE,
        isolation_profile="EPHEMERAL_PARTITION_NO_SHARED_COOKIES",
        started_at=now,
        expires_at=now + timedelta(minutes=10),
        evidence_stream_id=f"EVIDENCE-{identifier}",
        compute_meter_id=f"METER-{identifier}",
    )


def policy() -> BrowserPolicy:
    return BrowserPolicy(
        policy_id="POLICY-TEST-001",
        allowed_domains=["allowed.test"],
        allowed_actions=[BrowserActionType.NAVIGATE, BrowserActionType.READ_PAGE],
        high_impact_actions=[],
    )


def action(action_id: str, action_type: BrowserActionType, url: str) -> BrowserActionRequest:
    return BrowserActionRequest(
        action_id=action_id,
        action_type=action_type,
        target_url=url,
        purpose="TEST_ISOLATED_RUNTIME",
        data_classes=[],
    )


def executor(tmp_path) -> PlaywrightChromiumExecutor:
    return PlaywrightChromiumExecutor(
        chromium_executable=str(CHROMIUM),
        quarantine_root=tmp_path,
        route_fulfiller=fixture_route,
    )


def test_non_persistent_contexts_do_not_share_cookies(tmp_path) -> None:
    runtime = executor(tmp_path)
    first = session("ONE")
    second = session("TWO")
    browser_policy = policy()
    try:
        runtime.start_session(first, browser_policy)
        runtime.start_session(second, browser_policy)
        runtime.execute(
            first,
            action("ACTION-SET", BrowserActionType.NAVIGATE, f"{BASE_URL}/set-cookie"),
            browser_policy,
        )
        result = runtime.execute(
            second,
            action("ACTION-ECHO", BrowserActionType.READ_PAGE, f"{BASE_URL}/echo-cookie"),
            browser_policy,
        )
        assert result["text"] == "NONE"
    finally:
        runtime.close()


def test_context_route_blocks_non_allowlisted_network(tmp_path) -> None:
    runtime = executor(tmp_path)
    browser_session = session("BLOCK")
    browser_policy = policy()
    runtime.start_session(browser_session, browser_policy)
    try:
        with pytest.raises(ForbiddenError) as error:
            runtime.execute(
                browser_session,
                action("ACTION-BLOCKED", BrowserActionType.NAVIGATE, "https://blocked.test"),
                browser_policy,
            )
        assert "NETWORK_DOMAIN_BLOCKED" in error.value.reason_codes
    finally:
        runtime.close()


def test_pause_closes_runtime_context(tmp_path) -> None:
    runtime = executor(tmp_path)
    browser_session = session("PAUSE")
    browser_policy = policy()
    runtime.start_session(browser_session, browser_policy)
    runtime.pause_session(browser_session)
    try:
        with pytest.raises(StateConflictError):
            runtime.execute(
                browser_session,
                action("ACTION-AFTER-PAUSE", BrowserActionType.NAVIGATE, BASE_URL),
                browser_policy,
            )
    finally:
        runtime.close()


def test_quarantine_directories_are_owner_only(tmp_path) -> None:
    runtime = executor(tmp_path / "quarantine")
    browser_session = session("PERMISSIONS")
    browser_policy = policy()
    try:
        assert (runtime.quarantine_root.stat().st_mode & 0o777) == 0o700
        session_dir = runtime._session_directory(browser_session.browser_session_id)
        assert (session_dir.stat().st_mode & 0o777) == 0o700
    finally:
        runtime.close()
