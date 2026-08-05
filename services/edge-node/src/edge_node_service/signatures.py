from __future__ import annotations

from datetime import timezone
import hashlib
import hmac
import json
from typing import Protocol

from .models import HeartbeatRequest, SpoolEvent


class SecretResolver(Protocol):
    def resolve(self, credential_reference: str) -> bytes: ...


class UnavailableSecretResolver:
    def resolve(self, credential_reference: str) -> bytes:
        raise KeyError(credential_reference)


class StaticSecretResolver:
    def __init__(self, secrets: dict[str, bytes]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, credential_reference: str) -> bytes:
        try:
            return self._secrets[credential_reference]
        except KeyError as exc:
            raise KeyError(f"Unknown credential reference: {credential_reference}") from exc


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def heartbeat_signing_payload(node_id: str, heartbeat: HeartbeatRequest) -> bytes:
    return _canonical_json(
        {
            "node_id": node_id,
            "sequence": heartbeat.sequence,
            "sent_at": heartbeat.sent_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "agent_version": heartbeat.agent_version,
            "attestation_reference": heartbeat.attestation_reference,
            "runtime_digest": heartbeat.runtime_digest,
            "node_state": heartbeat.node_state.value,
            "metrics": heartbeat.metrics,
        }
    )


def sign_heartbeat(secret: bytes, node_id: str, heartbeat: HeartbeatRequest) -> str:
    return hmac.new(secret, heartbeat_signing_payload(node_id, heartbeat), hashlib.sha256).hexdigest()


def verify_heartbeat(secret: bytes, node_id: str, heartbeat: HeartbeatRequest) -> bool:
    expected = sign_heartbeat(secret, node_id, heartbeat)
    return hmac.compare_digest(expected, heartbeat.signature)


def spool_event_hash(event: SpoolEvent) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "event_id": event.event_id,
                "sequence": event.sequence,
                "event_type": event.event_type,
                "actor_id": event.actor_id,
                "occurred_at": event.occurred_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "payload": event.payload,
                "previous_local_hash": event.previous_local_hash,
            }
        )
    ).hexdigest()


def spool_batch_signing_payload(node_id: str, events: list[SpoolEvent]) -> bytes:
    return _canonical_json(
        {
            "node_id": node_id,
            "events": [
                {
                    "event_id": item.event_id,
                    "sequence": item.sequence,
                    "local_hash": item.local_hash,
                }
                for item in events
            ],
        }
    )


def sign_spool_batch(secret: bytes, node_id: str, events: list[SpoolEvent]) -> str:
    return hmac.new(secret, spool_batch_signing_payload(node_id, events), hashlib.sha256).hexdigest()


def verify_spool_batch(secret: bytes, node_id: str, events: list[SpoolEvent], signature: str) -> bool:
    expected = sign_spool_batch(secret, node_id, events)
    return hmac.compare_digest(expected, signature)
