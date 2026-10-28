from copy import deepcopy
from dataclasses import replace

import pytest

from genesis_gateway.ledger import hash_record
from genesis_gateway.spool_integrity import (
    EvidenceIntegrityError, SpoolRow, verify_rows
)
from genesis_gateway.warden_discovery import InvalidCatalog, discover


def catalog():
    return {
        "revision": "WARDEN-CATALOG-R02",
        "skills": [
            {"id": "WARDEN-Hawk-001", "status": "active",
             "capabilities": ["container.instance.restart"],
             "resource_ids": ["RES-GES-TEST"],
             "environments": ["staging"]},
            {"id": "WARDEN-Recall-002", "status": "revoked",
             "capabilities": ["container.instance.restart"],
             "resource_ids": ["RES-GES-TEST"],
             "environments": ["staging"]},
        ]
    }


def test_discovery_returns_candidates_but_cannot_authorize():
    result = discover(catalog(), capability="container.instance.restart",
                      resource_id="RES-GES-TEST", environment="staging")
    assert result.candidate_ids == ("WARDEN-Hawk-001",)
    assert not result.authorized and not result.execution_enabled
    assert result.reason_code == "WARDEN_AUTHORITY_NOT_CONNECTED"


def test_discovery_rejects_cross_environment_and_unknown_targets():
    assert not discover(catalog(), capability="container.instance.restart",
                        resource_id="RES-GES-TEST", environment="production").candidate_ids
    assert not discover(catalog(), capability="container.instance.restart",
                        resource_id="OTHER-RESOURCE", environment="staging").candidate_ids


def test_catalog_rejects_wildcards_duplicates_and_client_permits():
    for change in [
        lambda c: c["skills"][0]["resource_ids"].append("*"),
        lambda c: c["skills"].append(deepcopy(c["skills"][0])),
        lambda c: c["skills"][0].update({"permit": True}),
    ]:
        item = catalog()
        change(item)
        with pytest.raises(InvalidCatalog):
            discover(item, capability="container.instance.restart",
                     resource_id="RES-GES-TEST", environment="staging")


def rows():
    prev = None
    result = []
    for seq in (1, 2):
        event = {
            "schema_version": "genesis-gateway-evidence.r0.1",
            "event_type": "warden.decision.denied",
            "event_id": f"EVENT-{seq}",
            "intent": {"request_id": f"REQUEST-{seq}"},
            "issuer_id": "DIGITALME-CI",
            "result": "DENY",
            "execution_invoked": False,
        }
        digest = hash_record(event, prev)
        result.append(SpoolRow(seq, f"REQUEST-{seq}", f"EVENT-{seq}",
                               event, prev, digest))
        prev = digest
    return result


def test_full_chain_verified_but_not_independently_witnessed():
    sample = rows()
    attestation = verify_rows(sample, expected_head=sample[-1].record_hash)
    assert attestation["event_count"] == 2
    assert attestation["external_witnessed"] is False
    assert attestation["riveros_receipt"] is None


@pytest.mark.parametrize("mutation", [
    lambda r: [replace(r[1], seq=3), r[0]],
    lambda r: [r[1]],
    lambda r: [r[0], replace(r[1], previous_hash="0"*64)],
    lambda r: [r[0], replace(r[1], event={**r[1].event, "result": "PERMIT"})],
    lambda r: [r[0], replace(r[1], record_hash="0"*64)],
    lambda r: [r[0], replace(r[1], request_id=r[0].request_id)],
])
def test_spool_tampering_fails_closed(mutation):
    with pytest.raises(EvidenceIntegrityError):
        verify_rows(mutation(rows()))


def test_external_anchor_mismatch_rejected():
    with pytest.raises(EvidenceIntegrityError, match="EXTERNAL_ANCHOR_MISMATCH"):
        verify_rows(rows(), expected_head="0"*64)


def test_empty_spool_cannot_be_called_verified():
    with pytest.raises(EvidenceIntegrityError, match="EMPTY_SPOOL"):
        verify_rows([])


def test_unanchored_local_chain_is_not_reported_as_complete_or_witnessed():
    proof = verify_rows(rows())
    assert proof["verification"] == "local-chain-consistent-unanchored"
    assert proof["external_witnessed"] is False


def test_rolled_back_sequence_value_does_not_break_a_valid_hash_chain():
    pair = rows()
    pair[1] = replace(pair[1], seq=5)
    result = verify_rows(pair, expected_head=pair[-1].record_hash)
    assert result["event_count"] == 2
    assert result["last_seq"] == 5
