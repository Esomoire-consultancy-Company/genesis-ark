-- R0.1 gateway-owned append-only spool. Not the canonical RiverOS registry.
-- Apply using a scoped migration identity, not at web-service startup.
CREATE TABLE IF NOT EXISTS public.gateway_evidence (
    seq BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    event_id UUID NOT NULL UNIQUE,
    event JSONB NOT NULL,
    previous_hash CHAR(64),
    record_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The application DB role should have INSERT and SELECT only, with no
-- UPDATE, DELETE, TRUNCATE, DROP or ALTER permissions on this table.
-- Restrict schema ownership, extensions and migration credentials separately.
