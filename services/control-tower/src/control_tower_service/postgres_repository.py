from __future__ import annotations

from .postgres_base import PostgresControlTowerBase
from .postgres_capabilities import PostgresCapabilityVerifier
from .postgres_commands import PostgresCommandOperations
from .postgres_events import PostgresEventOperations
from .postgres_fleet import PostgresFleetOperations


class PostgresControlTowerRepository(
    PostgresFleetOperations,
    PostgresCommandOperations,
    PostgresEventOperations,
    PostgresCapabilityVerifier,
    PostgresControlTowerBase,
):
    """Authoritative PostgreSQL/Supabase Control Tower repository."""
