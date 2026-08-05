from __future__ import annotations

from .postgres_base import PostgresBase
from .postgres_fleet import PostgresFleetMixin
from .postgres_operations import PostgresOperationsMixin
from .postgres_publication import PostgresPublicationMixin


class PostgresControlTowerRepository(
    PostgresFleetMixin,
    PostgresOperationsMixin,
    PostgresPublicationMixin,
    PostgresBase,
):
    """Authoritative PostgreSQL/Supabase Control Tower repository."""


__all__ = ["PostgresControlTowerRepository"]
