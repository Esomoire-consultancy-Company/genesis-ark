"""Durable, tenant-scoped Warden source registration and consent grants.

Only callers with an independently verified work:admin identity context may
provision or revoke. Grant subjects cannot self-authorize. This is an Alpha
policy store, not a production policy authority service.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis_control_plane.work_gateway import AdmissionDenied, ConsentGrant, RegisteredSource
from genesis_control_plane.work_identity import IdentityContext

_CAPTURE_KINDS = frozenset({"work.input", "work.output", "work.tool", "work.revision"})
_ALLOWED_CHANNELS = frozenset({"typed", "voice_dictation", "voice_live", "api"})
_MAX_ID = 128


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_ID:
        raise AdmissionDenied("WARDEN_REGISTRY_ID_INVALID")
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@-" for c in value):
        raise AdmissionDenied("WARDEN_REGISTRY_ID_INVALID")
    return value


def _admin(ctx: IdentityContext, tenant: str, subject: str) -> None:
    if "work:admin" not in ctx.scopes:
        raise AdmissionDenied("WARDEN_ADMIN_SCOPE_REQUIRED")
    if ctx.tenant_id != tenant or ctx.subject == subject:
        raise AdmissionDenied("WARDEN_ADMIN_SELF_GRANT_DENIED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WardenConsentStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS source_registration (
                tenant_id TEXT NOT NULL, source TEXT NOT NULL,
                principal_id TEXT NOT NULL, station_id TEXT NOT NULL,
                channels_json TEXT NOT NULL, active INTEGER NOT NULL,
                version INTEGER NOT NULL,
                PRIMARY KEY(tenant_id, source, principal_id, station_id)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS consent_grant (
                consent_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                source TEXT NOT NULL, principal_id TEXT NOT NULL,
                station_id TEXT NOT NULL, work_id TEXT NOT NULL,
                kinds_json TEXT NOT NULL, valid_until TEXT NOT NULL,
                active INTEGER NOT NULL, version INTEGER NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS grant_scope ON consent_grant(tenant_id, principal_id, work_id)")

    def register_source(self, admin: IdentityContext, *, source: RegisteredSource) -> None:
        _admin(admin, source.tenant_id, source.principal_id)
        if admin.station_id != source.station_id:
            raise AdmissionDenied("WARDEN_ADMIN_STATION_DENIED")
        for field in (source.tenant_id, source.principal_id, source.station_id, source.source):
            _identifier(field)
        if not source.channels or not source.channels <= _ALLOWED_CHANNELS:
            raise AdmissionDenied("WARDEN_SOURCE_CHANNELS_INVALID")
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("""SELECT version FROM source_registration WHERE
                tenant_id=? AND source=? AND principal_id=? AND station_id=?""",
                (source.tenant_id, source.source, source.principal_id, source.station_id)).fetchone()
            conn.execute("""INSERT INTO source_registration
                (tenant_id, source, principal_id, station_id, channels_json, active, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id,source,principal_id,station_id) DO UPDATE SET
                channels_json=excluded.channels_json, active=excluded.active, version=excluded.version""",
                (source.tenant_id, source.source, source.principal_id, source.station_id,
                 json.dumps(sorted(source.channels)), int(source.active),
                 (row[0]+1) if row else 1))

    def register_grant(self, admin: IdentityContext, *, grant: ConsentGrant) -> None:
        _admin(admin, grant.tenant_id, grant.principal_id)
        if admin.station_id != grant.station_id:
            raise AdmissionDenied("WARDEN_ADMIN_STATION_DENIED")
        for field in (grant.consent_id, grant.tenant_id, grant.source,
                      grant.principal_id, grant.station_id, grant.work_id):
            _identifier(field)
        if (not grant.allowed_kinds or not grant.allowed_kinds <= _CAPTURE_KINDS):
            raise AdmissionDenied("WARDEN_GRANT_CAPABILITIES_INVALID")
        if grant.valid_until.tzinfo is None or grant.valid_until <= datetime.now(timezone.utc):
            raise AdmissionDenied("WARDEN_GRANT_TIME_DENIED")
        with sqlite3.connect(self.path) as conn:
            existing = conn.execute("""SELECT tenant_id,principal_id,station_id,source,work_id,version
                                       FROM consent_grant WHERE consent_id=?""", (grant.consent_id,)).fetchone()
            if existing and tuple(existing[:5]) != (
                grant.tenant_id, grant.principal_id, grant.station_id, grant.source, grant.work_id
            ):
                raise AdmissionDenied("WARDEN_GRANT_IMMUTABLE_SCOPE")
            conn.execute("""INSERT INTO consent_grant
                (consent_id,tenant_id,source,principal_id,station_id,work_id,
                 kinds_json,valid_until,active,version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(consent_id) DO UPDATE SET
                kinds_json=excluded.kinds_json,valid_until=excluded.valid_until,
                active=excluded.active,version=excluded.version""",
                (grant.consent_id, grant.tenant_id, grant.source, grant.principal_id,
                 grant.station_id, grant.work_id, json.dumps(sorted(grant.allowed_kinds)),
                 grant.valid_until.isoformat(), int(grant.active),
                 (existing[5]+1) if existing else 1))

    def revoke_grant(self, admin: IdentityContext, consent_id: str) -> None:
        _identifier(consent_id)
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT tenant_id, principal_id, station_id FROM consent_grant
                                  WHERE consent_id=?""", (consent_id,)).fetchone()
            if not row:
                raise AdmissionDenied("WARDEN_GRANT_NOT_FOUND")
            _admin(admin, row[0], row[1])
            if admin.station_id != row[2]:
                raise AdmissionDenied("WARDEN_ADMIN_STATION_DENIED")
            conn.execute("""UPDATE consent_grant SET active=0, version=version+1
                            WHERE consent_id=?""", (consent_id,))

    def revoke_source(self, admin: IdentityContext, source: RegisteredSource) -> None:
        _admin(admin, source.tenant_id, source.principal_id)
        if admin.station_id != source.station_id:
            raise AdmissionDenied("WARDEN_ADMIN_STATION_DENIED")
        with sqlite3.connect(self.path) as conn:
            result = conn.execute("""UPDATE source_registration SET active=0, version=version+1
                                    WHERE tenant_id=? AND source=? AND principal_id=? AND station_id=?""",
                                  (source.tenant_id, source.source, source.principal_id,
                                   source.station_id))
            if result.rowcount != 1:
                raise AdmissionDenied("WARDEN_SOURCE_NOT_FOUND")

    def resolve(self, actor: IdentityContext, *, work_id: str,
                now: datetime) -> tuple[RegisteredSource, ConsentGrant]:
        _identifier(work_id)
        if "work:capture" not in actor.scopes:
            raise AdmissionDenied("WARDEN_CAPTURE_SCOPE_REQUIRED")
        with sqlite3.connect(self.path) as conn:
            source_row = conn.execute("""SELECT channels_json,active FROM source_registration
                    WHERE tenant_id=? AND source=? AND principal_id=? AND station_id=?""",
                    (actor.tenant_id, actor.source, actor.subject, actor.station_id)).fetchone()
            if not source_row or not source_row[1]:
                raise AdmissionDenied("WARDEN_SOURCE_NOT_REGISTERED")
            rows = conn.execute("""SELECT consent_id,kinds_json,valid_until,active FROM consent_grant
                    WHERE tenant_id=? AND source=? AND principal_id=? AND station_id=? AND work_id=?""",
                    (actor.tenant_id, actor.source, actor.subject,
                     actor.station_id, work_id)).fetchall()
            active = []
            for consent_id, kinds, expiry, enabled in rows:
                if not enabled:
                    continue
                until = datetime.fromisoformat(expiry)
                if until.tzinfo is not None and until > now:
                    active.append((consent_id, frozenset(json.loads(kinds)), until))
            # No arbitrary selection if multiple grants are simultaneously active.
            if len(active) != 1:
                raise AdmissionDenied("WARDEN_UNAMBIGUOUS_CONSENT_REQUIRED")
            consent_id, kinds, expires = active[0]
            source = RegisteredSource(actor.tenant_id, actor.subject, actor.station_id,
                                      actor.source, frozenset(json.loads(source_row[0])), True)
            grant = ConsentGrant(consent_id, actor.tenant_id, actor.subject, actor.station_id,
                                 actor.source, work_id, expires, kinds, True)
            return source, grant
