from __future__ import annotations

from edge_node_service.models import SpoolFlushRequest
from edge_node_service.signatures import sign_spool_batch
from edge_node_service.spool import SQLiteEventSpool


def test_spool_batch_is_idempotent(
    tmp_path,
    enrolled_engine,
    secret_resolver,
):
    spool = SQLiteEventSpool(tmp_path / "idempotent.sqlite3")
    spool.append(event_type="LOCAL_EVENT", actor_id="edge-agent-001", payload={"value": 1})
    events = spool.pending()
    secret = secret_resolver.resolve("vault:edge/node-001")
    request = SpoolFlushRequest(
        events=events,
        batch_signature=sign_spool_batch(secret, "node-001", events),
    )
    first = enrolled_engine.ingest_spool("node-001", request)
    second = enrolled_engine.ingest_spool("node-001", request)
    assert first.accepted_event_ids == second.accepted_event_ids
    assert second.last_sequence == 1


def test_tampered_spool_event_is_rejected(tmp_path, enrolled_engine, secret_resolver):
    spool = SQLiteEventSpool(tmp_path / "tampered.sqlite3")
    event = spool.append(event_type="LOCAL_EVENT", actor_id="edge-agent-001", payload={"value": 1})
    tampered = event.model_copy(update={"payload": {"value": 2}})
    secret = secret_resolver.resolve("vault:edge/node-001")
    request = SpoolFlushRequest(
        events=[tampered],
        batch_signature=sign_spool_batch(secret, "node-001", [tampered]),
    )
    try:
        enrolled_engine.ingest_spool("node-001", request)
    except Exception as exc:
        assert "SPOOL_EVENT_HASH_INVALID" in exc.reason_codes
    else:
        raise AssertionError("tampered spool event was accepted")
