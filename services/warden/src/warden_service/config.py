from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Settings:
    api_token: str | None = None
    trusted_mtls_header: str = "x-client-cert-verified"
    trusted_mtls_value: str = "SUCCESS"
    policy_bundle_version: str = "warden-actor-box-v1.0.0"
    default_capability_ttl_seconds: int = 1200
    max_capability_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("WARDEN_API_TOKEN"),
            trusted_mtls_header=os.getenv(
                "WARDEN_TRUSTED_MTLS_HEADER", "x-client-cert-verified"
            ).lower(),
            trusted_mtls_value=os.getenv("WARDEN_TRUSTED_MTLS_VALUE", "SUCCESS"),
            policy_bundle_version=os.getenv(
                "WARDEN_POLICY_BUNDLE_VERSION", "warden-actor-box-v1.0.0"
            ),
            default_capability_ttl_seconds=int(
                os.getenv("WARDEN_DEFAULT_CAPABILITY_TTL_SECONDS", "1200")
            ),
            max_capability_ttl_seconds=int(
                os.getenv("WARDEN_MAX_CAPABILITY_TTL_SECONDS", "3600")
            ),
        )
