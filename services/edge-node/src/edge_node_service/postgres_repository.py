from __future__ import annotations

from .postgres_base import PostgresBase
from .postgres_commands import PostgresCommandMixin
from .postgres_evidence import PostgresEvidenceMixin


class PostgresEdgeNodeRepository(
    PostgresCommandMixin,
    PostgresEvidenceMixin,
    PostgresBase,
):
    """Authoritative PostgreSQL/Supabase Edge Node repository and capability verifier."""
