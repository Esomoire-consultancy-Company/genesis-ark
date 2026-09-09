from __future__ import annotations

import json
import secrets
import subprocess
from datetime import datetime
from typing import Callable

from genesis_control_plane.contracts import Command, ExecutionResult, ExecutionState
from genesis_control_plane.registry import RegistryResource


class UnsupportedCapabilityError(ValueError):
    pass


class DockerAdapter:
    def __init__(self, runner: Callable = subprocess.run):
        self._runner = runner

    def restart(
        self, resource: RegistryResource, command: Command, now: datetime
    ) -> ExecutionResult:
        if command.capability != "container.instance.restart":
            raise UnsupportedCapabilityError(command.capability)
        timeout = int(command.parameters.get("timeout_seconds", 30))
        if timeout < 1 or timeout > 300:
            raise ValueError("INVALID_TIMEOUT")
        args = [
            "docker",
            "restart",
            "--timeout",
            str(timeout),
            resource.docker_name,
        ]
        completed = self._runner(
            args,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            check=False,
            shell=False,
        )
        state = (
            ExecutionState.COMPLETED
            if completed.returncode == 0
            else ExecutionState.FAILED
        )
        return ExecutionResult(
            execution_id=f"EXEC-{secrets.token_hex(8)}",
            command_id=command.command_id,
            target_resource_id=resource.resource_id,
            state=state,
            exit_code=int(completed.returncode),
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
        )

    def inspect(self, resource: RegistryResource) -> list[dict]:
        completed = self._runner(
            ["docker", "inspect", resource.docker_name],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            return []
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []
