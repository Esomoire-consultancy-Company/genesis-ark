from __future__ import annotations

from dataclasses import dataclass
import os


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
        )
