"""Consent-based, metadata-only importer for ChatGPT conversation JSON exports.

No raw prompts, transcripts, image pointers, titles or filenames enter the
River journal. Historical typed/voice provenance is deliberately unknown.
Explicit --commit is needed before evidence is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile

from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.work_evidence import append_work_event, validate_payload

_JSON_NAME = re.compile(r"^conversations(?:[-_]\d+)?\.json$", re.IGNORECASE)
MAX_JSON_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


def _anonymous_id(kind: str, *parts: str) -> str:
    # Stable pseudonyms, not anonymity against guessing known source IDs.
    digest = hashlib.sha256(json.dumps([kind, *parts], separators=(",", ":")).encode()).hexdigest()[:32]
    return f"{kind}-{digest}"


def _read_json(raw: bytes) -> list[dict]:
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("WORK_IMPORT_FILE_TOO_LARGE")
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("WORK_IMPORT_BAD_JSON") from exc
    if isinstance(value, dict) and isinstance(value.get("conversations"), list):
        value = value["conversations"]
    if not isinstance(value, list):
        raise ValueError("WORK_IMPORT_EXPECTED_CONVERSATIONS_ARRAY")
    if not all(isinstance(v, dict) for v in value):
        raise ValueError("WORK_IMPORT_INVALID_CONVERSATION_ITEM")
    return value


def load_export(path: Path) -> list[dict]:
    """Load user-provided export without extracting archive files to disk."""
    if not path.is_file():
        raise ValueError("WORK_IMPORT_EXPORT_NOT_FOUND")
    if path.suffix.lower() == ".json":
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("WORK_IMPORT_FILE_TOO_LARGE")
        with path.open("rb") as handle:
            return _read_json(handle.read(MAX_JSON_BYTES + 1))
    if path.suffix.lower() != ".zip":
        raise ValueError("WORK_IMPORT_UNSUPPORTED_FILE_TYPE")
    result = []
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES or sum(e.file_size for e in entries) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError("WORK_IMPORT_ARCHIVE_TOO_LARGE")
            accepted = [e for e in entries if _JSON_NAME.fullmatch(e.filename.rsplit("/", 1)[-1]) and not e.is_dir()]
            if not accepted:
                raise ValueError("WORK_IMPORT_NO_CONVERSATIONS_JSON")
            for entry in accepted:
                if entry.file_size > MAX_JSON_BYTES:
                    raise ValueError("WORK_IMPORT_FILE_TOO_LARGE")
                if entry.file_size > 0 and entry.file_size > 1000 * max(1, entry.compress_size):
                    raise ValueError("WORK_IMPORT_SUSPICIOUS_COMPRESSION")
                with archive.open(entry) as handle:
                    result.extend(_read_json(handle.read(MAX_JSON_BYTES + 1)))
    except BadZipFile as exc:
        raise ValueError("WORK_IMPORT_BAD_ARCHIVE") from exc
    return result


def _is_contentful(message: dict) -> bool:
    content = message.get("content")
    if not isinstance(content, dict):
        return False
    parts = content.get("parts")
    if isinstance(parts, list) and parts:
        if any(isinstance(p, dict) or isinstance(p, str) and p.strip() for p in parts):
            return True
    metadata = message.get("metadata") or {}
    if isinstance(metadata, dict) and isinstance(metadata.get("attachments"), list) and metadata["attachments"]:
        return True
    return content.get("content_type") in {"audio", "audio_transcription", "multimodal_text", "image", "video"}


def _media_parts(message: dict, scope: str) -> tuple[list[str], list[dict]]:
    content = message.get("content") or {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    parts = parts if isinstance(parts, list) else []
    present: set[str] = set()
    assets: list[dict] = []

    def add(modality: str, locator: str) -> None:
        present.add(modality)
        asset_id = _anonymous_id("asset", scope, locator)
        if not any(x["asset_id"] == asset_id for x in assets):
            assets.append({"asset_id": asset_id, "modality": modality})

    for idx, part in enumerate(parts):
        if isinstance(part, str):
            if part.strip():
                present.add("text")
            continue
        if not isinstance(part, dict):
            continue
        typ = str(part.get("content_type") or part.get("type") or "").lower()
        if "image" in typ:
            modality = "image"
        elif "audio" in typ or "voice" in typ:
            modality = "audio"
        elif "video" in typ or "frame" in typ:
            modality = "video"
        elif "file" in typ:
            modality = "file"
        else:
            if isinstance(part.get("text"), str) and part["text"].strip():
                present.add("text")
            continue
        add(modality, f"{idx}:{modality}")
        if isinstance(part.get("text"), str) and part["text"].strip():
            present.add("text")

    if isinstance(content, dict):
        content_type = str(content.get("content_type") or "").lower()
        if "audio" in content_type or "voice" in content_type:
            present.add("audio")
        if content_type == "text" and any(isinstance(p, str) and p.strip() for p in parts):
            present.add("text")

    metadata = message.get("metadata") or {}
    attachments = metadata.get("attachments", []) if isinstance(metadata, dict) else []
    if isinstance(attachments, list):
        for idx, attachment in enumerate(attachments):
            if not isinstance(attachment, dict):
                continue
            name = str(attachment.get("name") or "").lower()
            mime = str(attachment.get("mime_type") or attachment.get("content_type") or "").lower()
            if mime.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".heic")):
                modality = "image"
            elif mime.startswith("audio/") or name.endswith((".mp3", ".wav", ".m4a", ".ogg")):
                modality = "audio"
            elif mime.startswith("video/") or name.endswith((".mp4", ".mov", ".webm")):
                modality = "video"
            else:
                modality = "file"
            add(modality, f"attachment:{idx}:{modality}")

    if len(assets) > 100:
        raise ValueError("WORK_IMPORT_TOO_MANY_ASSETS")
    if not present:
        present.add("text")  # unknown content variant, never source provenance
    return sorted(present), assets


def _role_message(node: Any) -> tuple[str | None, dict | None]:
    if not isinstance(node, dict):
        return None, None
    message = node.get("message")
    if not isinstance(message, dict):
        return None, None
    author = message.get("author")
    role = author.get("role") if isinstance(author, dict) else None
    if role not in {"user", "assistant"}:
        return None, None
    if role == "assistant":
        if message.get("recipient") not in (None, "all"):
            return None, None
        metadata = message.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("is_visually_hidden_from_conversation") is True:
            return None, None
    return role, message


def _nearest_user_parent(node: dict, mapping: dict, conv_id: str) -> str | None:
    """Walk branch ancestors; never link an answer to a different fork."""
    seen: set[str] = set()
    parent = node.get("parent")
    while isinstance(parent, str) and parent not in seen:
        seen.add(parent)
        ancestor = mapping.get(parent)
        if not isinstance(ancestor, dict):
            break
        role, msg = _role_message(ancestor)
        if role == "user" and msg is not None and _is_contentful(msg):
            return _anonymous_id("msg", conv_id, str(msg.get("id") or parent))
        parent = ancestor.get("parent")
    return None


def _source_timestamp(message: dict) -> str | None:
    value = message.get("create_time")
    try:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        if not 2000 <= dt.year <= 2100:
            return None
        return dt.isoformat()
    except (OverflowError, ValueError, OSError):
        return None


def compile_events(conversations: Iterable[dict], *, work_id: str | None = None) -> tuple[list[tuple[str, dict]], dict]:
    """Produce deterministic metadata; do not classify narration semantically."""
    events: list[tuple[str, dict]] = []
    counts = Counter()
    seen: dict[tuple[str, str, str], dict] = {}
    for conv in conversations:
        counts["conversations_seen"] += 1
        raw_conv_id = conv.get("id") or conv.get("conversation_id")
        if not isinstance(raw_conv_id, str) or not raw_conv_id.strip():
            counts["conversations_without_id"] += 1
            continue
        conv_id = raw_conv_id
        conv_key = _anonymous_id("chat", conv_id)
        wid = work_id or conv_key
        mapping = conv.get("mapping")
        if not isinstance(mapping, dict):
            counts["conversations_without_mapping"] += 1
            continue
        for node_id, node in mapping.items():
            role, msg = _role_message(node)
            if role is None or msg is None:
                continue
            if not _is_contentful(msg):
                counts["empty_messages_skipped"] += 1
                continue
            source_id = str(msg.get("id") or node_id)
            if role == "user":
                modalities, assets = _media_parts(msg, _anonymous_id("source", conv_id, source_id))
                kind = "work.input"
                payload = {"work_id": wid, "message_id": _anonymous_id("msg", conv_id, source_id),
                           "conversation_id": conv_key, "channel": "import_unknown", "provenance": "unknown",
                           "nature": "other", "modalities": modalities, "attachments": assets}
                counts["user_messages"] += 1
            else:
                kind = "work.output"
                payload = {"work_id": wid, "response_id": _anonymous_id("out", conv_id, source_id),
                           "conversation_id": conv_key}
                parent_id = _nearest_user_parent(node, mapping, conv_id)
                if parent_id:
                    payload["reply_to_message_id"] = parent_id
                else:
                    counts["outputs_without_user_parent"] += 1
                counts["assistant_outputs"] += 1
            timestamp = _source_timestamp(msg)
            if timestamp:
                payload["source_occurred_at"] = timestamp
            else:
                counts["messages_without_timestamp"] += 1
            validate_payload(kind, payload)
            key = (kind, wid, payload.get("message_id") or payload.get("response_id"))
            if key in seen:
                if seen[key] != payload:
                    raise ValueError("WORK_IMPORT_SOURCE_ID_CONFLICT")
                counts["duplicate_source_ids"] += 1
                continue
            seen[key] = payload
            events.append((kind, payload))
    return events, dict(counts)


def import_export(path: Path, *, journal_path: Path, principal_id: str,
                  station_id: str = "GES-ALPHA-001",
                  work_id: str | None = None, commit: bool = False) -> dict:
    """Default is read-only; caller-supplied principal is NOT authenticated."""
    for name, value in {"principal_id": principal_id, "station_id": station_id}.items():
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError(f"WORK_IMPORT_REQUIRED_{name.upper()}")
    if work_id is not None and (not isinstance(work_id, str) or not 0 < len(work_id) <= 256):
        raise ValueError("WORK_IMPORT_BAD_WORK_ID")
    events, counts = compile_events(load_export(path), work_id=work_id)
    journal = EvidenceJournal(journal_path)
    if not journal.verify_chain():
        raise ValueError("EVIDENCE_CHAIN_INVALID")
    existing = {}
    for record in journal._records():
        event = record.get("event", {})
        kind, p = event.get("event_type"), event.get("payload")
        if kind in {"work.input", "work.output"} and isinstance(p, dict):
            key = (kind, p.get("work_id"), p.get("message_id") or p.get("response_id"))
            if key in existing and existing[key] != p:
                raise ValueError("WORK_IMPORT_JOURNAL_CONFLICT")
            existing[key] = p
    missing = []
    duplicates = 0
    for kind, payload in events:
        key = (kind, payload["work_id"], payload.get("message_id") or payload.get("response_id"))
        if key in existing:
            if existing[key] != payload:
                raise ValueError("WORK_IMPORT_JOURNAL_CONFLICT")
            duplicates += 1
        else:
            missing.append((kind, payload))
    channels = Counter()
    modality_messages = Counter()
    attachments_by_modality = Counter()
    linked_reply_inputs = set()
    for kind, payload in events:
        if kind == "work.input":
            channels[payload["channel"]] += 1
            modality_messages.update(set(payload["modalities"]))
            attachments_by_modality.update(a["modality"] for a in payload.get("attachments", []))
        elif payload.get("reply_to_message_id"):
            linked_reply_inputs.add(payload["reply_to_message_id"])
    if commit:
        for kind, payload in missing:
            append_work_event(journal, kind=kind, payload=payload,
                              station_id=station_id, principal_id=principal_id,
                              session_id="CHATGPT-EXPORT-BACKFILL",
                              correlation_id=payload["conversation_id"],
                              source="chatgpt_export", classification="private")
    return {"mode": "commit" if commit else "preview", "source": "chatgpt_export",
            "conversations_seen": counts.get("conversations_seen", 0),
            "messages_identified": len(events), "new_events": len(missing),
            "already_recorded": duplicates,
            "user_messages": sum(1 for k, _ in events if k == "work.input"),
            "assistant_outputs": sum(1 for k, _ in events if k == "work.output"),
            "unknown_origin_user_messages": channels["import_unknown"],
            "channels": dict(channels), "messages_with_modality": dict(modality_messages),
            "attached_assets": dict(attachments_by_modality),
            "responded_input_messages": len(linked_reply_inputs),
            "missingness": {k: v for k, v in counts.items() if k.endswith("skipped") or
                            k.endswith("without_mapping") or k.endswith("without_user_parent") or
                            k.endswith("without_id") or k.endswith("without_timestamp")},
            "journal_verified": journal.verify_chain(),
            "notes": "Voice vs typed cannot be verified from this export; no raw message text saved."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or import ChatGPT conversation metadata to Genesis River")
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--principal-id", required=True)
    parser.add_argument("--station-id", default="GES-ALPHA-001")
    parser.add_argument("--work-id", help="Combine conversations into a nominated workstream; otherwise one work ID per chat")
    parser.add_argument("--commit", action="store_true", help="Explicitly persist metadata-only evidence events")
    args = parser.parse_args(argv)
    try:
        result = import_export(args.export, journal_path=args.journal,
                               principal_id=args.principal_id, station_id=args.station_id,
                               work_id=args.work_id, commit=args.commit)
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
