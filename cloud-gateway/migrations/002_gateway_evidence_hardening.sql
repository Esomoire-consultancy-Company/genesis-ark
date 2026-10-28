-- R0.2 gateway-only schema hardening; reviewed migration identity only.
DO $$
DECLARE column_count integer;
BEGIN
  IF to_regclass('public.gateway_evidence') IS NULL THEN
    RAISE EXCEPTION 'GATEWAY_EVIDENCE_TABLE_MISSING';
  END IF;
  SELECT count(*) INTO column_count FROM pg_attribute
    WHERE attrelid = 'public.gateway_evidence'::regclass
    AND attnum > 0 AND NOT attisdropped
    AND (
      (attname = 'seq' AND atttypid = 'pg_catalog.int8'::regtype AND attnotnull)
      OR (attname IN ('request_id', 'event_id') AND atttypid = 'pg_catalog.uuid'::regtype AND attnotnull)
      OR (attname = 'event' AND atttypid = 'pg_catalog.jsonb'::regtype AND attnotnull)
      OR (attname = 'previous_hash' AND atttypid = 'pg_catalog.bpchar'::regtype AND atttypmod = 68)
      OR (attname = 'record_hash' AND atttypid = 'pg_catalog.bpchar'::regtype AND atttypmod = 68 AND attnotnull)
      OR (attname = 'created_at' AND atttypid = 'pg_catalog.timestamptz'::regtype AND attnotnull)
    );
  IF column_count <> 7 OR
    (SELECT count(*) FROM pg_attribute
      WHERE attrelid = 'public.gateway_evidence'::regclass
      AND attnum > 0 AND NOT attisdropped) <> 7 THEN
    RAISE EXCEPTION 'GATEWAY_EVIDENCE_SCHEMA_MISMATCH';
  END IF;
END
$$;

-- Preserve an append-only single chain, including its null predecessor.
CREATE UNIQUE INDEX IF NOT EXISTS gateway_evidence_prev_unique_r02
  ON public.gateway_evidence (previous_hash)
  WHERE previous_hash IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS gateway_evidence_one_genesis_r02
  ON public.gateway_evidence ((1))
  WHERE previous_hash IS NULL;
CREATE INDEX IF NOT EXISTS gateway_evidence_created_at_r02
  ON public.gateway_evidence (created_at);

CREATE OR REPLACE FUNCTION public.gateway_evidence_reject_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'GATEWAY_EVIDENCE_APPEND_ONLY';
END
$$;
REVOKE ALL ON FUNCTION public.gateway_evidence_reject_mutation() FROM PUBLIC;
DROP TRIGGER IF EXISTS gateway_evidence_no_update_delete ON public.gateway_evidence;
CREATE TRIGGER gateway_evidence_no_update_delete
  BEFORE UPDATE OR DELETE ON public.gateway_evidence
  FOR EACH ROW EXECUTE FUNCTION public.gateway_evidence_reject_mutation();
DROP TRIGGER IF EXISTS gateway_evidence_no_truncate ON public.gateway_evidence;
CREATE TRIGGER gateway_evidence_no_truncate
  BEFORE TRUNCATE ON public.gateway_evidence
  FOR EACH STATEMENT EXECUTE FUNCTION public.gateway_evidence_reject_mutation();
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
