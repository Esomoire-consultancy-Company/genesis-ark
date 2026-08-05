from __future__ import annotations

from dataclasses import dataclass
import os


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip().lower() in {"", "none", "null"}:
        return None
    return int(value)


@dataclass(frozen=True, slots=True)
class Settings:
    api_token: str | None = None
    trusted_mtls_header: str = "x-client-cert-verified"
    trusted_mtls_value: str = "SUCCESS"
    policy_bundle_version: str = "warden-actor-box-v1.0.0"
    default_capability_ttl_seconds: int = 1200
    max_capability_ttl_seconds: int = 3600
    repository_backend: str = "memory"
    database_url: str | None = None
    database_pool_min_size: int = 1
    database_pool_max_size: int = 8
    database_pool_timeout_seconds: float = 10.0
    database_prepare_threshold: int | None = None

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
            repository_backend=os.getenv("WARDEN_REPOSITORY_BACKEND", "memory").lower(),
            database_url=os.getenv("WARDEN_DATABASE_URL"),
            database_pool_min_size=int(os.getenv("WARDEN_DATABASE_POOL_MIN_SIZE", "1")),
            database_pool_max_size=int(os.getenv("WARDEN_DATABASE_POOL_MAX_SIZE", "8")),
            database_pool_timeout_seconds=float(
                os.getenv("WARDEN_DATABASE_POOL_TIMEOUT_SECONDS", "10")
            ),
            database_prepare_threshold=_optional_int(
                os.getenv("WARDEN_DATABASE_PREPARE_THRESHOLD")
            ),
        )
