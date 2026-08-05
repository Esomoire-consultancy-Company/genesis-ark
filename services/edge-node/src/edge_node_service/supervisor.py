from __future__ import annotations

from typing import Any, Protocol

from .errors import StateConflictError
from .models import CommandType, EdgeCommand


class SupervisorAdapter(Protocol):
    def execute(self, command: EdgeCommand) -> dict[str, Any]: ...
    def snapshot(self) -> dict[str, Any]: ...


class DeterministicSupervisor:
    """A no-host-access supervisor used for tests and contract environments."""

    def __init__(self) -> None:
        self.instances: dict[str, str] = {}
        self.sessions: dict[str, str] = {}
        self.node_state = "ACTIVE"
        self.agent_version = "0.1.0"

    def snapshot(self) -> dict[str, Any]:
        return {
            "instances": dict(sorted(self.instances.items())),
            "sessions": dict(sorted(self.sessions.items())),
            "node_state": self.node_state,
            "agent_version": self.agent_version,
        }

    def execute(self, command: EdgeCommand) -> dict[str, Any]:
        target = command.target_reference
        if command.command_type == CommandType.START_INSTANCE:
            if self.instances.get(target) == "RUNNING":
                return {"instance_id": target, "state": "RUNNING", "idempotent": True}
            self.instances[target] = "RUNNING"
            return {"instance_id": target, "state": "RUNNING"}
        if command.command_type == CommandType.STOP_INSTANCE:
            self.instances[target] = "STOPPED"
            return {"instance_id": target, "state": "STOPPED"}
        if command.command_type == CommandType.PAUSE_SESSION:
            self.sessions[target] = "PAUSED"
            return {"session_id": target, "state": "PAUSED"}
        if command.command_type == CommandType.TERMINATE_SESSION:
            self.sessions[target] = "TERMINATED"
            return {"session_id": target, "state": "TERMINATED"}
        if command.command_type == CommandType.EXECUTE_RECOVERY:
            self.instances[target] = "RECOVERED"
            return {"instance_id": target, "state": "RECOVERED"}
        if command.command_type == CommandType.ROTATE_AGENT:
            requested = str(command.payload.get("agent_version", "")).strip()
            if not requested:
                raise StateConflictError(
                    "ROTATE_AGENT requires payload.agent_version",
                    reason_codes=["AGENT_VERSION_REQUIRED"],
                )
            self.agent_version = requested
            return {"agent_version": requested, "state": "ROTATED"}
        if command.command_type == CommandType.DRAIN_NODE:
            self.node_state = "DRAINING"
            return {"node_state": self.node_state}
        raise StateConflictError(
            "Unsupported command type",
            reason_codes=["COMMAND_TYPE_UNSUPPORTED"],
        )
