from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .errors import StateConflictError
from .models import CapabilityAuthorization, ControlTowerEvent, FleetAsset, FleetCommand, Incident
from .postgres_base import _decode_fields, _decode_json

class PostgresCapabilityVerifier:
    def verify(
        self,
        *,
        capability_id: str,
        box_id: str,
        principal_id: str,
        context_id: str,
        resource_id: str,
        required_actions: set[str],
        purpose: str,
        at,
    ) -> CapabilityAuthorization | None:
        allowed = tuple(required_actions | {"CONTROL_TOWER_MANAGE", "*"})
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select capability_id, box_id, subject_id, context_id, resource_id,
                       allowed_action, purpose, expires_at, constraints
                from public.active_capability_grants
                where capability_id = %s
                  and box_id = %s
                  and subject_id = %s
                  and context_id = %s
                  and resource_id in (%s, %s, '*')
                  and purpose = %s
                  and allowed_action = any(%s)
                  and expires_at > %s
                """,
                (
                    capability_id,
                    box_id,
                    principal_id,
                    context_id,
                    resource_id,
                    box_id,
                    purpose,
                    list(allowed),
                    at,
                ),
            )
        decoded = _decode_fields(row, "constraints")
        return CapabilityAuthorization.model_validate(decoded) if decoded else None
