"""R0.4 externally verified identity -> Warden grant -> River admission.

Library-only reference service. Never expose the internal trusted-claims
gateway method as a public API route; entry points must verify access tokens.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis_control_plane.work_consent import WardenConsentStore, _identifier
from genesis_control_plane.work_gateway import AdmissionDenied, WorkIntakeGateway
from genesis_control_plane.work_identity import DigitalMeAccessVerifier, IdentityContext


class DigitalMeWorkFabric:
    def __init__(
        self, *, verifier: DigitalMeAccessVerifier, consent: WardenConsentStore,
        source_key_resolver, ledger_path: Path, journal_path: Path,
    ):
        """source_key_resolver(tenant_id, source) returns server-held adapter key.

        The resolver must be a trusted backend implementation, not user data.
        """
        self.verifier, self.consent = verifier, consent
        self.source_key_resolver = source_key_resolver
        self.ledger_path, self.journal_path = ledger_path, journal_path

    def _identity(self, token: str, *, scope: str,
                  now: datetime | None = None) -> IdentityContext:
        return self.verifier.verify(token, required_scope=scope, now=now)

    def capture(self, *, access_token: str, packet: dict, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        identity = self._identity(access_token, scope="work:capture", now=now)
        if not isinstance(packet, dict) or not isinstance(packet.get("payload"), dict):
            raise AdmissionDenied("GATEWAY_PACKET_MALFORMED")
        work_id = _identifier(packet["payload"].get("work_id"))
        source, grant = self.consent.resolve(identity, work_id=work_id, now=now)
        key = self.source_key_resolver(identity.tenant_id, identity.source)
        if not isinstance(key, bytes) or len(key) < 32:
            raise AdmissionDenied("GATEWAY_SOURCE_KEY_UNAVAILABLE")
        gateway = WorkIntakeGateway(
            ledger_path=self.ledger_path, journal_path=self.journal_path,
            identity_signing_key=None, source_signing_key=key,
            source=source, grant=grant,
        )
        claims = dict(tenant_id=identity.tenant_id, principal_id=identity.principal_id,
                      station_id=identity.station_id, source=identity.source,
                      session_id=identity.session_id)
        return gateway._admit_trusted_claims(claims=claims, packet=packet, now=now)

    def private_counts(self, *, access_token: str, work_id: str,
                       now: datetime | None = None) -> dict[str, Any]:
        """Only indexed and authenticated own work. Not a raw event reader."""
        identity = self._identity(access_token, scope="work:read", now=now)
        work_id = _identifier(work_id)
        if not self.ledger_path.is_file() or not self.journal_path.is_file():
            raise AdmissionDenied("GATEWAY_EVIDENCE_NOT_READY")
        from genesis_control_plane.evidence import EvidenceJournal
        journal = EvidenceJournal(self.journal_path)
        if not journal.verify_chain():
            raise AdmissionDenied("GATEWAY_RIVER_CHAIN_INVALID")
        with sqlite3.connect(f"file:{self.ledger_path.as_posix()}?mode=ro", uri=True, timeout=10) as db:
            rows = db.execute("""SELECT event_id,record_hash FROM accepted_work
                                  WHERE tenant_id=? AND principal_id=? AND work_id=?""",
                              (identity.tenant_id, identity.principal_id, work_id)).fetchall()
        chain = {}
        for item in journal._records():
            event = item.get("event", {})
            event_id = event.get("event_id")
            if event_id in chain:
                raise AdmissionDenied("GATEWAY_DUPLICATE_RIVER_EVENT")
            chain[event_id] = item
        observed = Counter()
        modalities = Counter()
        assets = Counter()
        event_counts = Counter()
        message_ids = set()
        response_ids = set()
        replied_to = set()
        for event_id, record_hash in rows:
            record = chain.get(event_id)
            if not record or record.get("record_hash") != record_hash:
                raise AdmissionDenied("GATEWAY_READ_RECEIPT_MISMATCH")
            ev = record["event"]
            p = ev.get("payload", {})
            if (not isinstance(p, dict) or
                p.get("tenant_id") != identity.tenant_id or
                p.get("work_id") != work_id or
                ev.get("principal_id") != identity.principal_id):
                raise AdmissionDenied("GATEWAY_READ_SCOPE_MISMATCH")
            kind = ev.get("event_type")
            event_counts[kind] += 1
            if kind == "work.input":
                message_ids.add(p["message_id"])
                if p.get("provenance") == "observed":
                    observed[p["channel"]] += 1
                modalities.update(set(p.get("modalities", [])))
                assets.update(a["modality"] for a in p.get("attachments", []))
            elif kind == "work.output":
                response_ids.add(p["response_id"])
                if p.get("reply_to_message_id"):
                    replied_to.add(p["reply_to_message_id"])
        return {
            "tenant_id": identity.tenant_id, "principal_id": identity.principal_id,
            "work_id": work_id, "receipt_count": len(rows),
            "input_messages": len(message_ids), "assistant_outputs": len(response_ids),
            "responded_inputs": len(message_ids & replied_to),
            "channels_observed": dict(observed),
            "messages_with_modality": dict(modalities),
            "attached_assets": dict(assets),
            "recorded_tool_invocations": event_counts["work.tool"],
            "recorded_revisions": event_counts["work.revision"],
            "verified": False, "finalized": False,
            "privacy_scope": "tenant+principal+work",
        }
