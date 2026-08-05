from __future__ import annotations

from typing import Any, Protocol

from .models import BrowserActionRequest, BrowserSession


class BrowserExecutor(Protocol):
    def execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
    ) -> dict[str, Any]: ...


class DeterministicBrowserExecutor:
    """Non-network executor used until an isolated browser runtime is attached."""

    def execute(
        self,
        session: BrowserSession,
        action: BrowserActionRequest,
    ) -> dict[str, Any]:
        return {
            "executor": "DETERMINISTIC_BROKER",
            "browser_session_id": session.browser_session_id,
            "action_type": action.action_type,
            "target_url": str(action.target_url) if action.target_url else None,
            "executed": True,
        }
