"""Additive, privacy-minimizing work evidence counters for the Genesis River journal.

This module never guesses whether a transcript was typed or spoken. It relies
on explicitly supplied source provenance and records no conversation content.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from genesis_control_plane.contracts import EvidenceEvent
from genesis_control_plane.evidence import EvidenceJournal, EvidenceReceipt

CHANNELS = frozenset({"typed", "voice_dictation", "voice_live", "api", "import_unknown"})
MODALITIES = frozenset({"text", "image", "audio", "video", "file"})
NATURES = frozenset({"narration", "command", "question", "feedback", "evidence", "other"})
PROVENANCE = frozenset({"observed", "inferred", "unknown"})
KINDS = frozenset({"work.input", "work.output", "work.tool", "work.revision", "work.verified", "work.approved", "work.finalized", "work.reopened"})
REQUIRED = {
    "work.input": "message_id", "work.output": "response_id", "work.tool": "tool_call_id",
    "work.revision": "revision_id", "work.verified": "deliverable_id",
    "work.approved": "deliverable_id", "work.finalized": "deliverable_id",
    "work.reopened": "deliverable_id",
}
FIELDS = {
    "work.input": frozenset({"work_id", "message_id", "channel", "provenance", "nature", "modalities", "attachments", "conversation_id", "parent_message_id", "capture_id", "source_occurred_at"}),
    "work.output": frozenset({"work_id", "response_id", "reply_to_message_id", "conversation_id", "deliverable_id", "capture_id", "source_occurred_at"}),
    "work.tool": frozenset({"work_id", "tool_call_id", "capability", "outcome", "execution_id", "command_id", "capture_id"}),
    "work.revision": frozenset({"work_id", "revision_id", "parent_response_id", "deliverable_id", "capture_id"}),
    "work.verified": frozenset({"work_id", "deliverable_id", "verification_receipt_id"}),
    "work.approved": frozenset({"work_id", "deliverable_id", "approval_receipt_id"}),
    "work.finalized": frozenset({"work_id", "deliverable_id", "version"}),
    "work.reopened": frozenset({"work_id", "deliverable_id", "version"}),
}


def _required_str(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"WORK_EVIDENCE_REQUIRED_{name.upper()}")
    return value


def validate_payload(kind: str, payload: Mapping[str, Any]) -> None:
    if kind not in KINDS:
        raise ValueError("WORK_EVIDENCE_UNSUPPORTED_EVENT")
    _required_str(payload, "work_id")
    _required_str(payload, REQUIRED[kind])
    if any(key not in FIELDS[kind] for key in payload):
        raise ValueError("WORK_EVIDENCE_RAW_CONTENT_FORBIDDEN")
    if kind == "work.input":
        channel = payload.get("channel")
        provenance = payload.get("provenance")
        if channel not in CHANNELS or provenance not in PROVENANCE:
            raise ValueError("WORK_EVIDENCE_BAD_ORIGIN")
        if provenance == "unknown" and channel != "import_unknown":
            raise ValueError("WORK_EVIDENCE_UNSUPPORTED_ORIGIN_CLAIM")
        if channel == "import_unknown" and provenance != "unknown":
            raise ValueError("WORK_EVIDENCE_UNSUPPORTED_ORIGIN_CLAIM")
        if payload.get("nature") not in NATURES:
            raise ValueError("WORK_EVIDENCE_BAD_NATURE")
        media = payload.get("modalities", [])
        if not isinstance(media, list) or not media or len(media) > 5 or any(x not in MODALITIES for x in media):
            raise ValueError("WORK_EVIDENCE_BAD_MODALITIES")
        attachments = payload.get("attachments", [])
        if not isinstance(attachments, list) or len(attachments) > 100:
            raise ValueError("WORK_EVIDENCE_BAD_ATTACHMENTS")
        seen = set()
        for item in attachments:
            if not isinstance(item, dict) or set(item) != {"asset_id", "modality"}:
                raise ValueError("WORK_EVIDENCE_BAD_ATTACHMENTS")
            identifier = _required_str(item, "asset_id")
            if identifier in seen or item.get("modality") not in MODALITIES or item["modality"] not in media:
                raise ValueError("WORK_EVIDENCE_BAD_ATTACHMENTS")
            seen.add(identifier)
    if kind == "work.output" and "reply_to_message_id" in payload:
        _required_str(payload, "reply_to_message_id")


def append_work_event(
    journal: EvidenceJournal, *, kind: str, payload: Mapping[str, Any],
    station_id: str, principal_id: str, session_id: str,
    correlation_id: str, source: str, classification: str = "internal",
    causation_id: str | None = None,
) -> EvidenceReceipt:
    """Write one metadata-only event via the existing tamper-evident River journal.

    Source adapters capture origin at input time; historical exports with no
    origin must use import_unknown.
    """
    validate_payload(kind, payload)
    for key, value in {"station_id": station_id, "principal_id": principal_id,
                       "session_id": session_id, "correlation_id": correlation_id,
                       "source": source}.items():
        if not value or not isinstance(value, str):
            raise ValueError(f"WORK_EVIDENCE_REQUIRED_{key.upper()}")
    return journal.append(EvidenceEvent(
        event_id=str(uuid4()), event_type=kind, schema_version="work-0.1",
        occurred_at=datetime.now(timezone.utc).isoformat(), station_id=station_id,
        principal_id=principal_id, session_id=session_id, source=source,
        subject=payload["work_id"], payload=dict(payload),
        correlation_id=correlation_id, causation_id=causation_id,
        classification=classification,
    ))


def summarize_work_journal(path: Path, work_id: str) -> dict[str, Any]:
    """Count verified journal records, without reading or retaining prompt text.

    Finalized means linked verification and approval precede finalization.
    Warden remains responsible for the authenticity of those receipts.
    """
    if not EvidenceJournal(path).verify_chain():
        raise ValueError("EVIDENCE_CHAIN_INVALID")
    unique_events: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)["event"]
            if ev.get("event_type") not in KINDS or ev.get("payload", {}).get("work_id") != work_id:
                continue
            validate_payload(ev["event_type"], ev["payload"])
            event_id = ev["event_id"]
            if event_id in unique_events:
                if unique_events[event_id] != ev:
                    raise ValueError("WORK_EVIDENCE_EVENT_ID_CONFLICT")
                continue
            unique_events[event_id] = ev
    inputs: dict[str, dict] = {}
    outputs: dict[str, dict] = {}
    tools: set[str] = set()
    revisions: set[str] = set()
    approvals: set[str] = set()
    verifications: set[str] = set()
    finalized: set[str] = set()
    reopened: set[str] = set()
    for ev in unique_events.values():
        kind, p = ev["event_type"], ev["payload"]
        if kind == "work.input":
            key, destination = p["message_id"], inputs
        elif kind == "work.output":
            key, destination = p["response_id"], outputs
        else:
            key, destination = None, None
        if destination is not None:
            if key in destination and destination[key] != p:
                raise ValueError("WORK_EVIDENCE_RECORD_CONFLICT")
            destination[key] = p
        elif kind == "work.tool":
            tools.add(p["tool_call_id"])
        elif kind == "work.revision":
            revisions.add(p["revision_id"])
        elif kind == "work.verified":
            verifications.add(p["deliverable_id"])
        elif kind == "work.approved":
            approvals.add(p["deliverable_id"])
        elif kind == "work.finalized":
            item = p["deliverable_id"]
            if item in approvals and item in verifications:
                finalized.add(item)
        elif kind == "work.reopened":
            reopened.add(p["deliverable_id"])
            finalized.discard(p["deliverable_id"])
            # A revised deliverable needs fresh verification and acceptance.
            approvals.discard(p["deliverable_id"])
            verifications.discard(p["deliverable_id"])
    confirmed, unconfirmed = Counter(), Counter()
    natures, modalities, media_assets = Counter(), Counter(), Counter()
    for p in inputs.values():
        target = confirmed if p["provenance"] == "observed" else unconfirmed
        target[p["channel"]] += 1
        natures[p["nature"]] += 1
        modalities.update(set(p["modalities"]))
        media_assets.update(a["modality"] for a in p.get("attachments", []))
    round_trips = {p.get("reply_to_message_id") for p in outputs.values()} & set(inputs)
    return {
        "work_id": work_id, "input_messages": len(inputs),
        "assistant_outputs": len(outputs), "responded_inputs": len(round_trips),
        "tool_invocations": len(tools), "revision_requests": len(revisions),
        "approved_deliverables": len(approvals), "verified_deliverables": len(verifications),
        "finalized_deliverables": len(finalized), "reopened_deliverables": len(reopened),
        "channels_observed": dict(confirmed), "channels_unverified": dict(unconfirmed),
        "input_natures": dict(natures), "messages_with_modality": dict(modalities),
        "attached_assets": dict(media_assets), "evidence_events": len(unique_events),
    }
