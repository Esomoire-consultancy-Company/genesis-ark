from __future__ import annotations

import secrets
from datetime import datetime

from genesis_control_plane.contracts import (
    ExecutionResult,
    ExecutionState,
    VerificationResult,
    VerificationState,
)
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.registry import RegistryResource


class DockerVerifier:
    def __init__(self, adapter: DockerAdapter):
        self._adapter = adapter

    def verify_restart(
        self,
        resource: RegistryResource,
        execution: ExecutionResult,
        now: datetime,
    ) -> VerificationResult:
        observed_state = "unknown"
        state = VerificationState.NOT_VERIFIED
        if execution.state is ExecutionState.COMPLETED:
            data = self._adapter.inspect(resource)
            if len(data) == 1:
                item = data[0]
                name_matches = item.get("Name") in {
                    resource.docker_name,
                    f"/{resource.docker_name}",
                }
                runtime_state = item.get("State") or {}
                running = runtime_state.get("Running") is True
                health = runtime_state.get("Health")
                health_ok = health is None or health.get("Status") == "healthy"
                observed_state = (
                    "healthy" if running and health_ok else "unhealthy"
                )
                if name_matches and running and health_ok:
                    state = VerificationState.VERIFIED
        return VerificationResult(
            verification_id=f"VER-{secrets.token_hex(8)}",
            execution_id=execution.execution_id,
            target_resource_id=resource.resource_id,
            state=state,
            observed_state=observed_state,
            verified_at=now.isoformat(),
        )
