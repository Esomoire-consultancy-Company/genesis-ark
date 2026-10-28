from genesis_gateway.ledger import hash_record, canonical_json


def test_hash_chain_is_order_stable_and_tamper_evident():
    event = {"event_type": "warden.decision.denied", "issuer_id": "DIGITALME-ACTOR-CI"}
    assert hash_record(event, None) == hash_record(dict(reversed(list(event.items()))), None)
    first = hash_record(event, None)
    next_hash = hash_record({"event_type": "another"}, first)
    assert next_hash != hash_record({"event_type": "another"}, "0" * 64)
    assert next_hash != first


def test_canonical_json_does_not_depend_on_key_order():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
