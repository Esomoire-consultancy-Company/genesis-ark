from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.contracts import Command


def test_canonical_json_is_order_independent():
    left = canonical_json({"b": 2, "a": 1})
    right = canonical_json({"a": 1, "b": 2})
    assert left == right == '{"a":1,"b":2}'


def test_sha256_hex_is_stable():
    assert sha256_hex("abc") == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_command_is_immutable():
    command = Command(
        command_id="CMD-001",
        correlation_id="CORR-001",
        principal_id="DM-001",
        session_id="SES-001",
        station_id="GES-ALPHA-001",
        adapter_id="GEN-ADAPTER-DOCKER-001",
        target_resource_id="RES-RIVER-WORKER-001",
        capability="container.instance.restart",
        parameters={"timeout_seconds": 30},
        risk_class="medium",
        environment="alpha",
        requested_at="2026-09-09T08:00:00+05:30",
        expires_at="2026-09-09T08:02:00+05:30",
    )
    try:
        command.station_id = "OTHER"
    except Exception:
        pass
    else:
        raise AssertionError("Command must be immutable")
