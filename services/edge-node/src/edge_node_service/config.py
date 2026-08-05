from __future__ import annotations

from dataclasses import dataclass
import os


def _required_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _required_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip().lower() in {"", "none", "null"}:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("EDGE_NODE_DATABASE_PREPARE_THRESHOLD must be an integer or null") from exc


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
    heartbeat_max_clock_skew_seconds: int = 120
    default_command_lease_seconds: int = 60
    max_command_lease_seconds: int = 300
    max_command_attempts: int = 5

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
        if self.heartbeat_max_clock_skew_seconds < 1:
            raise ValueError("heartbeat_max_clock_skew_seconds must be positive")
        if not 1 <= self.default_command_lease_seconds <= self.max_command_lease_seconds <= 300:
            raise ValueError("command lease seconds must satisfy 1 <= default <= max <= 300")
        if self.max_command_attempts < 1:
            raise ValueError("max_command_attempts must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("EDGE_NODE_API_TOKEN"),
            trusted_mtls_header=os.getenv(
                "EDGE_NODE_TRUSTED_MTLS_HEADER", "x-client-cert-verified"
            ).lower(),
            trusted_mtls_value=os.getenv("EDGE_NODE_TRUSTED_MTLS_VALUE", "SUCCESS"),
            repository_backend=os.getenv("EDGE_NODE_REPOSITORY_BACKEND", "memory"),
            database_url=os.getenv("EDGE_NODE_DATABASE_URL"),
            database_pool_min_size=_required_int("EDGE_NODE_DATABASE_POOL_MIN_SIZE", "1"),
            database_pool_max_size=_required_int("EDGE_NODE_DATABASE_POOL_MAX_SIZE", "8"),
            database_pool_timeout_seconds=_required_float(
                "EDGE_NODE_DATABASE_POOL_TIMEOUT_SECONDS", "10"
            ),
            database_prepare_threshold=_optional_int(
                os.getenv("EDGE_NODE_DATABASE_PREPARE_THRESHOLD")
            ),
            heartbeat_max_clock_skew_seconds=_required_int(
                "EDGE_NODE_HEARTBEAT_MAX_CLOCK_SKEW_SECONDS", "120"
            ),
            default_command_lease_seconds=_required_int(
                "EDGE_NODE_DEFAULT_COMMAND_LEASE_SECONDS", "60"
            ),
            max_command_lease_seconds=_required_int(
                "EDGE_NODE_MAX_COMMAND_LEASE_SECONDS", "300"
            ),
            max_command_attempts=_required_int("EDGE_NODE_MAX_COMMAND_ATTEMPTS", "5"),
        )
