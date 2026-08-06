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
    warden_base_url: str = "http://127.0.0.1:8080"
    warden_api_token: str | None = None
    default_session_ttl_seconds: int = 1800
    max_session_ttl_seconds: int = 3600
    approval_ttl_seconds: int = 300
    repository_backend: str = "memory"
    database_url: str | None = None
    database_pool_min_size: int = 1
    database_pool_max_size: int = 8
    database_pool_timeout_seconds: float = 10.0
    database_prepare_threshold: int | None = None
    executor_mode: str = "DETERMINISTIC"
    chromium_executable: str | None = None
    chromium_headless: bool = True
    quarantine_root: str = "/tmp/genesis-cloudbrowser"
    executor_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("CLOUDBROWSER_API_TOKEN"),
            trusted_mtls_header=os.getenv(
                "CLOUDBROWSER_TRUSTED_MTLS_HEADER", "x-client-cert-verified"
            ).lower(),
            trusted_mtls_value=os.getenv(
                "CLOUDBROWSER_TRUSTED_MTLS_VALUE", "SUCCESS"
            ),
            warden_base_url=os.getenv(
                "CLOUDBROWSER_WARDEN_BASE_URL", "http://127.0.0.1:8080"
            ),
            warden_api_token=os.getenv("CLOUDBROWSER_WARDEN_API_TOKEN"),
            default_session_ttl_seconds=int(
                os.getenv("CLOUDBROWSER_DEFAULT_SESSION_TTL_SECONDS", "1800")
            ),
            max_session_ttl_seconds=int(
                os.getenv("CLOUDBROWSER_MAX_SESSION_TTL_SECONDS", "3600")
            ),
            approval_ttl_seconds=int(
                os.getenv("CLOUDBROWSER_APPROVAL_TTL_SECONDS", "300")
            ),
            repository_backend=os.getenv(
                "CLOUDBROWSER_REPOSITORY_BACKEND", "memory"
            ).lower(),
            database_url=os.getenv("CLOUDBROWSER_DATABASE_URL"),
            database_pool_min_size=int(
                os.getenv("CLOUDBROWSER_DATABASE_POOL_MIN_SIZE", "1")
            ),
            database_pool_max_size=int(
                os.getenv("CLOUDBROWSER_DATABASE_POOL_MAX_SIZE", "8")
            ),
            database_pool_timeout_seconds=float(
                os.getenv("CLOUDBROWSER_DATABASE_POOL_TIMEOUT_SECONDS", "10")
            ),
            database_prepare_threshold=_optional_int(
                os.getenv("CLOUDBROWSER_DATABASE_PREPARE_THRESHOLD")
            ),
            executor_mode=os.getenv(
                "CLOUDBROWSER_EXECUTOR_MODE", "DETERMINISTIC"
            ).upper(),
            chromium_executable=os.getenv("CLOUDBROWSER_CHROMIUM_EXECUTABLE"),
            chromium_headless=os.getenv(
                "CLOUDBROWSER_CHROMIUM_HEADLESS", "true"
            ).lower()
            in {"1", "true", "yes", "on"},
            quarantine_root=os.getenv(
                "CLOUDBROWSER_QUARANTINE_ROOT", "/tmp/genesis-cloudbrowser"
            ),
            executor_timeout_seconds=float(
                os.getenv("CLOUDBROWSER_EXECUTOR_TIMEOUT_SECONDS", "30")
            ),
        )
