from __future__ import annotations

from dataclasses import dataclass
import os


def _required_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _required_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip().lower() in {"", "none", "null"}:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer or null") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    api_token: str | None = None
    trusted_mtls_header: str = "x-client-cert-verified"
    trusted_mtls_value: str = "SUCCESS"
    repository_backend: str = "memory"
    database_url: str | None = None
    database_pool_min_size: int = 1
    database_pool_max_size: int = 8
    database_pool_timeout_seconds: float = 10.0
    database_prepare_threshold: int | None = None
    degraded_after_seconds: int = 90
    offline_after_seconds: int = 300
    publication_default_lease_seconds: int = 60
    publication_max_lease_seconds: int = 600

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_token", (self.api_token or "").strip() or None)
        backend = self.repository_backend.strip().lower()
        object.__setattr__(self, "repository_backend", backend)
        object.__setattr__(self, "trusted_mtls_header", self.trusted_mtls_header.strip().lower())
        if backend not in {"memory", "postgres"}:
            raise ValueError("repository_backend must be 'memory' or 'postgres'")
        if backend == "postgres" and not (self.database_url or "").strip():
            raise ValueError("database_url is required for the postgres backend")
        if not self.trusted_mtls_header or not self.trusted_mtls_value:
            raise ValueError("trusted mTLS header and value must be non-empty")
        if self.database_pool_min_size < 1:
            raise ValueError("database_pool_min_size must be at least 1")
        if self.database_pool_max_size < self.database_pool_min_size:
            raise ValueError("database_pool_max_size must be >= database_pool_min_size")
        if self.database_pool_timeout_seconds <= 0:
            raise ValueError("database_pool_timeout_seconds must be positive")
        if self.database_prepare_threshold is not None and self.database_prepare_threshold < 0:
            raise ValueError("database_prepare_threshold must be non-negative or null")
        if not (1 <= self.degraded_after_seconds < self.offline_after_seconds):
            raise ValueError("heartbeat thresholds must satisfy 1 <= degraded < offline")
        if not (1 <= self.publication_default_lease_seconds <= self.publication_max_lease_seconds <= 3600):
            raise ValueError("publication leases must satisfy 1 <= default <= max <= 3600")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("CONTROL_TOWER_API_TOKEN"),
            trusted_mtls_header=os.getenv("CONTROL_TOWER_TRUSTED_MTLS_HEADER", "x-client-cert-verified"),
            trusted_mtls_value=os.getenv("CONTROL_TOWER_TRUSTED_MTLS_VALUE", "SUCCESS"),
            repository_backend=os.getenv("CONTROL_TOWER_REPOSITORY_BACKEND", "memory"),
            database_url=os.getenv("CONTROL_TOWER_DATABASE_URL"),
            database_pool_min_size=_required_int("CONTROL_TOWER_DATABASE_POOL_MIN_SIZE", "1"),
            database_pool_max_size=_required_int("CONTROL_TOWER_DATABASE_POOL_MAX_SIZE", "8"),
            database_pool_timeout_seconds=_required_float("CONTROL_TOWER_DATABASE_POOL_TIMEOUT_SECONDS", "10"),
            database_prepare_threshold=_optional_int("CONTROL_TOWER_DATABASE_PREPARE_THRESHOLD"),
            degraded_after_seconds=_required_int("CONTROL_TOWER_DEGRADED_AFTER_SECONDS", "90"),
            offline_after_seconds=_required_int("CONTROL_TOWER_OFFLINE_AFTER_SECONDS", "300"),
            publication_default_lease_seconds=_required_int("CONTROL_TOWER_PUBLICATION_DEFAULT_LEASE_SECONDS", "60"),
            publication_max_lease_seconds=_required_int("CONTROL_TOWER_PUBLICATION_MAX_LEASE_SECONDS", "600"),
        )
