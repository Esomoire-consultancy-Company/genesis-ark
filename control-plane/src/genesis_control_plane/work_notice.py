"""R0.6 notice-bound member consent adapter.

A browser MUST explicitly affirm the displayed notice and its exact version.
This is not legal-signature proof, not an OIDC login, and not a deployed UI.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from genesis_control_plane.canonical import sha256_hex
from genesis_control_plane.work_consent import _identifier
from genesis_control_plane.work_gateway import AdmissionDenied
from genesis_control_plane.work_r05 import WorkEvidenceStaging

NOTICE_VERSION = "GWIEP-NOTICE-R0.6"
NOTICE_TEXT = (
    "With your permission, Genesis can record metadata about work you submit "
    "within this authorized workstream, including whether an authorized client "
    "observed typed, dictated or live voice inputs, file/image attachment counts, "
    "assistant output and task/tool receipts. Raw prompts, audio and images are "
    "not stored in this work-evidence ledger. You can withdraw permission; "
    "previously projected receipts follow applicable retention and deletion rules. "
    "Nothing is collected from your private ChatGPT history automatically."
)
NOTICE_HASH = sha256_hex(NOTICE_TEXT)


class WorkNoticeConsent:
    """Same local staging database; no external network or browser session API."""
    def __init__(self, staging: WorkEvidenceStaging):
        self.staging = staging
        with sqlite3.connect(staging.db_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS notice_acceptance (
                receipt_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL, principal_id TEXT NOT NULL,
                source TEXT NOT NULL, work_id TEXT NOT NULL,
                version TEXT NOT NULL, notice_hash TEXT NOT NULL,
                token_id_hash TEXT NOT NULL, at TEXT NOT NULL,
                linked_consent_receipt TEXT NOT NULL
            )""")

    @staticmethod
    def notice() -> dict[str, str]:
        return {"version": NOTICE_VERSION, "purpose": "work_evidence_capture",
                "text": NOTICE_TEXT, "sha256": NOTICE_HASH}

    def opt_in(self, *, access_token: str, work_id: str, expires_at: datetime,
               notice_version: str, affirmative: bool, now: datetime | None = None) -> dict:
        current = now or datetime.now(timezone.utc)
        actor = self.staging._identity(access_token, "work:consent", current)
        work_id = _identifier(work_id)
        if affirmative is not True or notice_version != NOTICE_VERSION:
            raise AdmissionDenied("R06_NOTICE_ACCEPTANCE_REQUIRED")
        # Staging verifies expiry, purpose, subject scope, and records durable
        # consent. Notice is recorded subsequently; a failed notice write must
        # not report success, and operations must reconcile before deployment.
        granted = self.staging.opt_in(access_token=access_token, work_id=work_id,
                                       expires_at=expires_at, now=current)
        rid = "GWIEP-NOTICE-" + uuid4().hex
        with sqlite3.connect(self.staging.db_path) as db:
            db.execute("""INSERT INTO notice_acceptance
                (receipt_id,tenant_id,principal_id,source,work_id,version,
                 notice_hash,token_id_hash,at,linked_consent_receipt)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (rid, actor.tenant_id, actor.subject, actor.source,
                 work_id, NOTICE_VERSION, NOTICE_HASH,
                 sha256_hex(actor.token_id), current.isoformat(), granted["receipt_id"]))
        return {**granted, "notice_receipt_id": rid,
                "notice_version": NOTICE_VERSION, "notice_sha256": NOTICE_HASH}
