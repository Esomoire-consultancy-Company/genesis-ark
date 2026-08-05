from __future__ import annotations

from dataclasses import dataclass
import os


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip().lower() in {"", "none", "null"}:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("RUNTIME_MANAGER_DATABASE_PREPARE_THRESHOLD must be an integer or null") from exc


def _required_int(name: str, default: str) -> int:
    value = os.getenv(name, default)
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _required_float(name: str, default: str) -> float:
    value = os.getenv(name, default)
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


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
    default_session_ttl_seconds: int = 1800
    max_session_ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        token = self.api_token.strip() if self.api_token is not None else None
        object.__setattr__(self, "api_token", token or None)
        backend = self.repository_backend.strip().lower()
        object.__setattr__(self, "repository_backend", backend)
        if backend not in {"memory", "postgres"}:
            raise ValueError("repository_backend must be 'memory' or 'postgres'")
        if backend == "postgres" and not (self.database_url or "").strip():
            raise ValueError("database_url is required for the postgres backend")
        if not self.trusted_mtls_header.strip() or not self.trusted_mtls_value:
            raise ValueError("trusted mTLS header and value must be non-empty")
        if self.database_pool_min_size < 1:
            raise ValueError("database_pool_min_size must be at least 1")
        if self.database_pool_max_size < self.database_pool_min_size:
            raise ValueError("database_pool_max_size must be >= database_pool_min_size")
        if self.database_pool_timeout_seconds <= 0:
            raise ValueError("database_pool_timeout_seconds must be positive")
        if self.database_prepare_threshold is not None and self.database_prepare_threshold < 0:
            raise ValueError("database_prepare_threshold must be non-negative or null")
        if not (
            1
            <= self.default_session_ttl_seconds
            <= self.max_session_ttl_seconds
            <= 3600
        ):
            raise ValueError(
                "session TTLs must satisfy 1 <= default <= max <= 3600"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("RUNTIME_MANAGER_API_TOKEN"),
            trusted_mtls_header=os.getenv(
                "RUNTIME_MANAGER_TRUSTED_MTLS_HEADER", "x-client-cert-verified"
            ).lower(),
            trusted_mtls_value=os.getenv(
                "RUNTIME_MANAGER_TRUSTED_MTLS_VALUE", "SUCCESS"
            ),
            repository_backend=os.getenv(
                "RUNTIME_MANAGER_REPOSITORY_BACKEND", "memory"
            ),
            database_url=os.getenv("RUNTIME_MANAGER_DATABASE_URL"),
            database_pool_min_size=_required_int(
                "RUNTIME_MANAGER_DATABASE_POOL_MIN_SIZE", "1"
            ),
            database_pool_max_size=_required_int(
                "RUNTIME_MANAGER_DATABASE_POOL_MAX_SIZE", "8"
            ),
            database_pool_timeout_seconds=_required_float(
                "RUNTIME_MANAGER_DATABASE_POOL_TIMEOUT_SECONDS", "10"
            ),
            database_prepare_threshold=_optional_int(
                os.getenv("RUNTIME_MANAGER_DATABASE_PREPARE_THRESHOLD")
            ),
            default_session_ttl_seconds=_required_int(
                "RUNTIME_MANAGER_DEFAULT_SESSION_TTL_SECONDS", "1800"
            ),
            max_session_ttl_seconds=_required_int(
                "RUNTIME_MANAGER_MAX_SESSION_TTL_SECONDS", "3600"
            ),
        )
