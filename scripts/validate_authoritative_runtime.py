#!/usr/bin/env python3
"""Offline safety checks for the authoritative Warden/CloudBrowser slice."""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing required artifact: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is None:
        raise AssertionError(f"Missing authoritative control: {label}")


def main() -> None:
    migration = read("db/authoritative/v1/003_authoritative_runtime_hardening.sql")
    warden_repo = read("services/warden/src/warden_service/postgres_repository.py")
    browser_repo = read("services/cloudbrowser/src/cloudbrowser_service/postgres_repository.py")
    browser_executor = read("services/cloudbrowser/src/cloudbrowser_service/executor.py")
    browser_engine = read("services/cloudbrowser/src/cloudbrowser_service/engine.py")
    warden_config = read("services/warden/src/warden_service/config.py")
    browser_config = read("services/cloudbrowser/src/cloudbrowser_service/config.py")
    warden_package = read("services/warden/pyproject.toml")
    browser_package = read("services/cloudbrowser/pyproject.toml")
    warden_dockerfile = read("services/warden/Dockerfile")
    browser_dockerfile = read("services/cloudbrowser/Dockerfile")

    expected_tables = {
        "actor_boxes", "actor_box_bindings", "box_runtimes", "box_contexts",
        "warden_policy_profiles", "consent_receipts", "delegated_agents",
        "warden_policy_decisions", "capability_grants", "data_boundary_rules",
        "box_evidence_events", "box_revocations", "box_recovery_authorities",
        "warden_unbound_evidence_events", "warden_unbound_decisions",
        "cloud_browser_policies", "cloud_browser_sessions", "cloud_browser_actions",
        "cloud_browser_approvals", "cloud_browser_usage", "cloud_browser_evidence_events",
    }
    for table in sorted(expected_tables):
        require(migration, rf"alter\s+table\s+{re.escape(table)}\s+enable\s+row\s+level\s+security", f"RLS enabled for {table}")
        require(migration, rf"create\s+policy\s+genesis_control_plane_internal_access\s+on\s+{re.escape(table)}", f"private control-plane policy for {table}")

    require(migration, r"create\s+role\s+genesis_control_plane\s+nologin", "NOLOGIN backend role")
    require(migration, r"revoke\s+all\s+on\s+table[\s\S]+from\s+anon,\s*authenticated", "public role revocation")
    require(migration, r"security_invoker\s*=\s*true", "security-invoker views")
    require(migration, r"create\s+table\s+if\s+not\s+exists\s+warden_unbound_decisions", "unbound deny ledger")
    require(migration, r"create\s+index\s+if\s+not\s+exists\s+box_evidence_latest_lookup", "Box evidence chain index")
    require(migration, r"create\s+index\s+if\s+not\s+exists\s+cloud_browser_evidence_latest_lookup", "browser evidence chain index")

    for source, label in ((warden_repo, "Warden repository"), (browser_repo, "CloudBrowser repository")):
        require(source, r"pg_advisory_xact_lock", f"{label} advisory transaction lock")
        require(source, r"ConnectionPool", f"{label} connection pool")
        require(source, r"prepare_threshold", f"{label} prepared-statement control")
        require(source, r"autocommit\"\s*:\s*False", f"{label} transactional connections")

    require(warden_repo, r"warden_unbound_evidence_events", "unbound evidence persistence")
    require(warden_repo, r"warden_unbound_decisions", "unbound decision persistence")
    require(browser_repo, r"record_approval_grant", "approval grant transaction")
    require(browser_engine, r"BROWSER_ACTION_AUTHORIZED", "durable pre-execution authorization")
    require(browser_engine, r"Action ID was reused with a different request", "action idempotency conflict")

    require(browser_executor, r"ThreadPoolExecutor\(max_workers=1", "Playwright thread affinity")
    require(browser_executor, r"browser\.new_context", "non-persistent BrowserContext")
    require(browser_executor, r"service_workers=\"block\"", "service-worker blocking")
    require(browser_executor, r"context\.route\(\"\*\*/\*\"", "context-wide network interception")
    require(browser_executor, r"FILE_OUTSIDE_QUARANTINE", "quarantine path enforcement")
    require(browser_executor, r"chmod\(0o700\)", "owner-only quarantine permissions")
    require(browser_executor, r"permissions=\[\]", "empty Chromium permission set")
    if "--no-sandbox" in browser_executor:
        raise AssertionError("Chromium sandbox must not be disabled in source")

    for config, label in ((warden_config, "Warden"), (browser_config, "CloudBrowser")):
        require(config, r"database_prepare_threshold:\s*int\s*\|\s*None\s*=\s*None", f"{label} transaction-pool-safe default")

    if 'psycopg[binary,pool]==3.3.4' not in warden_package:
        raise AssertionError("Warden psycopg production dependency is not pinned")
    if 'psycopg[binary,pool]==3.3.4' not in browser_package:
        raise AssertionError("CloudBrowser psycopg production dependency is not pinned")
    if 'playwright==1.61.0' not in browser_package:
        raise AssertionError("CloudBrowser Playwright production dependency is not pinned")

    require(warden_dockerfile, r"USER\s+warden", "non-root Warden container")
    require(browser_dockerfile, r"USER\s+pwuser", "non-root CloudBrowser container")
    require(browser_dockerfile, r"v1\.61\.0-noble", "matching Playwright container")
    if "--no-sandbox" in browser_dockerfile:
        raise AssertionError("CloudBrowser container must not disable the Chromium sandbox")

    print("Authoritative Warden and CloudBrowser runtime controls validated successfully.")


if __name__ == "__main__":
    main()
