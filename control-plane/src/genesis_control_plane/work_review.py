"""R0.6 independent Warden two-person grant review; source/test only.

Neither a proposed grant nor a single approval authorizes an operation.
All callers are independently verified by the configured access-token verifier.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from genesis_control_plane.work_consent import WardenConsentStore, _identifier
from genesis_control_plane.work_gateway import AdmissionDenied, ConsentGrant, RegisteredSource
from genesis_control_plane.work_identity import DigitalMeAccessVerifier, IdentityContext

_KINDS = frozenset({"work.input", "work.output", "work.tool", "work.revision"})
_CHANNELS = frozenset({"typed", "voice_dictation", "voice_live", "api"})


class WardenReviewQueue:
    def __init__(self, path: Path, *, verifier: DigitalMeAccessVerifier,
                 registry: WardenConsentStore):
        self.path = path
        self.verifier = verifier
        self.registry = registry
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS grant_reviews (
                proposal_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                proposer_id TEXT NOT NULL, target_id TEXT NOT NULL,
                station_id TEXT NOT NULL, source TEXT NOT NULL, work_id TEXT NOT NULL,
                channels_json TEXT NOT NULL, kinds_json TEXT NOT NULL,
                expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','applying','approved','rejected')),
                approver_id TEXT, reviewed_at TEXT
            )""")

    def _actor(self, token: str, *, scope: str, now: datetime) -> IdentityContext:
        return self.verifier.verify(token, required_scope=scope, now=now)

    @staticmethod
    def _admin(actor: IdentityContext, target: str) -> None:
        if "work:admin" not in actor.scopes or actor.subject == target:
            raise AdmissionDenied("R06_ADMIN_AUTHORITY_DENIED")

    def propose(self, *, access_token: str, target_id: str, source: str,
                work_id: str, channels: list[str], kinds: list[str],
                expires_at: datetime, now: datetime) -> dict:
        actor = self._actor(access_token, scope="work:admin", now=now)
        target_id, source, work_id = map(_identifier, (target_id, source, work_id))
        self._admin(actor, target_id)
        if (not isinstance(channels, list) or not channels or
            len(channels) != len(set(channels)) or not set(channels) <= _CHANNELS):
            raise AdmissionDenied("R06_CHANNELS_INVALID")
        if (not isinstance(kinds, list) or not kinds or
            len(kinds) != len(set(kinds)) or not set(kinds) <= _KINDS):
            raise AdmissionDenied("R06_KINDS_INVALID")
        if (expires_at.tzinfo is None or expires_at <= now or
            expires_at > now + __import__("datetime").timedelta(days=30)):
            raise AdmissionDenied("R06_EXPIRY_INVALID")
        proposal_id = "GWIEP-RVW-" + uuid4().hex
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO grant_reviews
                (proposal_id,tenant_id,proposer_id,target_id,station_id,source,work_id,
                 channels_json,kinds_json,expires_at,created_at,status)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending')""",
                (proposal_id, actor.tenant_id, actor.subject, target_id,
                 actor.station_id, source, work_id,
                 json.dumps(sorted(channels)), json.dumps(sorted(kinds)),
                 expires_at.isoformat(), now.isoformat()))
        return {"proposal_id": proposal_id, "status": "pending", "work_id": work_id}

    def approve(self, *, access_token: str, proposal_id: str, now: datetime) -> dict:
        actor = self._actor(access_token, scope="work:approve", now=now)
        _identifier(proposal_id)
        if "work:admin" not in actor.scopes:
            raise AdmissionDenied("R06_ADMIN_AUTHORITY_DENIED")
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT tenant_id,proposer_id,target_id,station_id,source,
                work_id,channels_json,kinds_json,expires_at,status FROM grant_reviews
                WHERE proposal_id=?""", (proposal_id,)).fetchone()
            if not row:
                raise AdmissionDenied("R06_PROPOSAL_UNKNOWN")
            tenant, proposer, target, station, source, work, channels, kinds, expiry, status = row
            if actor.tenant_id != tenant or actor.station_id != station:
                raise AdmissionDenied("R06_ADMIN_SCOPE_DENIED")
            if len({actor.subject, proposer, target}) != 3:
                raise AdmissionDenied("R06_INDEPENDENT_APPROVER_REQUIRED")
            if status != "pending":
                raise AdmissionDenied("R06_PROPOSAL_NOT_PENDING")
            expiration = datetime.fromisoformat(expiry)
            if expiration <= now:
                raise AdmissionDenied("R06_PROPOSAL_EXPIRED")
            # Fail closed in the event of interruption. Administrator must
            # reconcile a stuck 'applying' row; never automatically reissue.
            db.execute("""UPDATE grant_reviews SET status='applying',approver_id=?,
                reviewed_at=? WHERE proposal_id=?""",
                (actor.subject, now.isoformat(), proposal_id))
        registration = RegisteredSource(tenant, target, station, source,
                                        frozenset(json.loads(channels)))
        grant = ConsentGrant(proposal_id, tenant, target, station, source,
                             work, expiration, frozenset(json.loads(kinds)))
        # These are legacy R0.4 stores; cross-store atomicity is not claimed.
        self.registry.register_source(actor, source=registration)
        self.registry.register_grant(actor, grant=grant)
        with sqlite3.connect(self.path) as db:
            db.execute("""UPDATE grant_reviews SET status='approved'
                WHERE proposal_id=? AND status='applying'""", (proposal_id,))
        return {"proposal_id": proposal_id, "status": "approved", "work_id": work}

    def status(self, *, access_token: str, proposal_id: str,
               now: datetime) -> dict:
        actor = self._actor(access_token, scope="work:admin", now=now)
        _identifier(proposal_id)
        with sqlite3.connect(self.path) as db:
            row = db.execute("""SELECT tenant_id,proposer_id,status,work_id
                FROM grant_reviews WHERE proposal_id=?""", (proposal_id,)).fetchone()
        if not row or row[0] != actor.tenant_id:
            raise AdmissionDenied("R06_PROPOSAL_NOT_VISIBLE")
        return {"proposal_id": proposal_id, "proposer_id": row[1],
                "status": row[2], "work_id": row[3]}
