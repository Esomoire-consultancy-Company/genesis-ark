"""One-shot staging DB bootstrap. Never invoked by the Gateway web process.

Requires an explicitly supplied administration DSN and a strong application
password in the caller's environment. Do not use this utility in production
without separate migration/change-control review.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import psycopg
from psycopg import sql

DEFAULT_MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "001_gateway_evidence.sql"


def provision_staging(
    admin_dsn: str,
    role_name: str,
    role_password: str,
    migration_path: Path = DEFAULT_MIGRATION,
) -> None:
    if not re.fullmatch(r"genesis_gateway_[a-z0-9_]{2,32}", role_name):
        raise ValueError("INVALID_RUNTIME_ROLE_NAME")
    if len(role_password) < 32:
        raise ValueError("WEAK_RUNTIME_ROLE_PASSWORD")
    if not admin_dsn:
        raise ValueError("ADMIN_DSN_REQUIRED")

    migration = migration_path.read_text(encoding="utf-8")
    with psycopg.connect(admin_dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
            if cur.fetchone():
                # Prevent accidental password changes / reuse of unverified roles.
                raise ValueError("RUNTIME_ROLE_ALREADY_EXISTS")

            cur.execute(migration)
            role = sql.Identifier(role_name)
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(
                    role, sql.Literal(role_password)
                )
            )
            cur.execute("REVOKE ALL ON TABLE public.gateway_evidence FROM PUBLIC")
            cur.execute("REVOKE ALL ON SEQUENCE public.gateway_evidence_seq_seq FROM PUBLIC")
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
            cur.execute(sql.SQL("GRANT SELECT, INSERT ON TABLE public.gateway_evidence TO {}").format(role))
            cur.execute(sql.SQL("GRANT USAGE ON SEQUENCE public.gateway_evidence_seq_seq TO {}").format(role))
    # Transaction commit occurs only after every grant succeeds.


def main() -> None:
    dsn = os.environ.get("GENESIS_MIGRATION_ADMIN_DATABASE_URL", "")
    role = os.environ.get("GENESIS_GATEWAY_RUNTIME_ROLE", "")
    password = os.environ.get("GENESIS_GATEWAY_DB_PASSWORD", "")
    if not dsn or not role or not password:
        raise SystemExit("Missing required migration environment variables")
    provision_staging(dsn, role, password)
    print("STAGING_EVIDENCE_MIGRATION_APPLIED")  # No connection values or passwords.


if __name__ == "__main__":
    main()
