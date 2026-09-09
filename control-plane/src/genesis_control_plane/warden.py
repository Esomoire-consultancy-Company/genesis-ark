from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from genesis_control_plane.contracts import Command, Decision, DecisionResult
from genesis_control_plane.registry import AlphaRegistry, RegistryLookupError

RISK_SCORE = {"low": 1, "medium": 3, "high": 6, "critical": 10}


@dataclass(frozen=True)
class WardenPolicy:
    policy_id: str = "WARDEN-ENGINEERING-R0.1"
    max_risk: int = 3
    station_id: str = "GES-ALPHA-001"
    environment: str = "alpha"


class Warden:
    def __init__(self, registry: AlphaRegistry, policy: WardenPolicy):
        self._registry = registry
        self._policy = policy

    def _decision(self, command: Command, now: datetime, result: DecisionResult, reason: str) -> Decision:
        try:
            command_expiry = datetime.fromisoformat(command.expires_at)
        except ValueError:
            command_expiry = now
        valid_until = min(now + timedelta(seconds=60), command_expiry)
        return Decision(
            decision_id=f"WD-{secrets.token_hex(8)}",
            command_id=command.command_id,
            result=result,
            policy_id=self._policy.policy_id,
            conditions=("alpha_only", "one_shot_token") if result is DecisionResult.PERMIT else (),
            obligations=("evidence_required",) if result is DecisionResult.PERMIT else (),
            decided_at=now.isoformat(),
            valid_until=valid_until.isoformat(),
            reason_code=reason,
        )

    def evaluate(self, command: Command, now: datetime) -> Decision:
        try:
            command_expiry = datetime.fromisoformat(command.expires_at)
        except ValueError:
            return self._decision(command, now, DecisionResult.DENY, "COMMAND_TIME_INVALID")
        if command_expiry <= now:
            return self._decision(command, now, DecisionResult.DENY, "COMMAND_EXPIRED")
        if command.station_id != self._policy.station_id:
            return self._decision(command, now, DecisionResult.DENY, "STATION_DENIED")
        if command.environment != self._policy.environment:
            return self._decision(command, now, DecisionResult.DENY, "ENVIRONMENT_DENIED")
        if RISK_SCORE.get(command.risk_class, 10) > self._policy.max_risk:
            return self._decision(command, now, DecisionResult.DENY, "RISK_DENIED")
        try:
            self._registry.capability(command.capability)
        except RegistryLookupError:
            return self._decision(command, now, DecisionResult.DENY, "UNKNOWN_CAPABILITY")
        try:
            self._registry.resource(command.target_resource_id)
        except RegistryLookupError:
            return self._decision(command, now, DecisionResult.DENY, "UNKNOWN_TARGET")
        if not self._registry.supports(command.target_resource_id, command.capability, command.adapter_id):
            return self._decision(command, now, DecisionResult.DENY, "REGISTRY_BINDING_DENIED")
        return self._decision(command, now, DecisionResult.PERMIT, "PERMITTED")
