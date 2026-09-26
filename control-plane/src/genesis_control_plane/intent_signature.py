"""Independent, optional actor-intent signature verification for the Alpha control plane.

The caller supplies a signature, never its own trusted public key. The injected
resolver must return a currently admitted key from Genesis for this principal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from genesis_control_plane.canonical import canonical_json
from genesis_control_plane.contracts import Command


@dataclass(frozen=True)
class SignedCommandIntent:
    principal_id: str
    key_id: str
    nonce: str
    expires_at: str
    signature_hex: str


class ActorKeyResolver(Protocol):
    def active_ed25519_key(self, principal_id: str, key_id: str, at: datetime) -> bytes | None:
        """Resolve an admitted, active 32-byte public key; return None otherwise."""


def intent_bytes(command: Command, intent: SignedCommandIntent) -> bytes:
    """Domain-separated canonical bytes signed by the actor's admitted key."""
    return canonical_json({
        "domain": "GENESIS-ALPHA-COMMAND-INTENT-v1",
        "command": asdict(command),
        "principal_id": intent.principal_id,
        "key_id": intent.key_id,
        "nonce": intent.nonce,
        "expires_at": intent.expires_at,
    }).encode("utf-8")


class IntentSignatureVerifier:
    def __init__(self, keys: ActorKeyResolver):
        self._keys = keys

    def verify(self, command: Command, intent: SignedCommandIntent | None, now: datetime) -> str | None:
        """Return a stable denial code or None; this never grants Warden authority."""
        if intent is None:
            return "SIGNED_INTENT_REQUIRED"
        if intent.principal_id != command.principal_id or not intent.key_id or not intent.nonce:
            return "SIGNED_INTENT_CONTEXT_MISMATCH"
        try:
            if now.tzinfo is None:
                return "SIGNED_INTENT_TIME_INVALID"
            expiry = datetime.fromisoformat(intent.expires_at)
            if expiry.tzinfo is None:
                return "SIGNED_INTENT_TIME_INVALID"
            if expiry.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
                return "SIGNED_INTENT_EXPIRED"
            command_expiry = datetime.fromisoformat(command.expires_at)
            if command_expiry.tzinfo is None or expiry > command_expiry:
                return "SIGNED_INTENT_OUTLIVES_COMMAND"
            public_bytes = self._keys.active_ed25519_key(command.principal_id, intent.key_id, now)
            if public_bytes is None:
                return "SIGNING_KEY_NOT_ADMITTED"
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(
                bytes.fromhex(intent.signature_hex), intent_bytes(command, intent)
            )
        except (ValueError, TypeError, InvalidSignature):
            return "SIGNED_INTENT_INVALID"
        return None
