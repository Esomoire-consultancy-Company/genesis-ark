import pytest

from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.work_evidence import append_work_event, summarize_work_journal


def add(journal, kind, **payload):
    return append_work_event(
        journal, kind=kind, payload={"work_id": "W-01", **payload},
        station_id="GES-ALPHA-001", principal_id="DM-001",
        session_id="SES-001", correlation_id="COR-001", source="test",
    )


def test_multimodal_input_counted_once_assets_counted_separately(tmp_path):
    path = tmp_path / "river.jsonl"
    j = EvidenceJournal(path)
    add(j, "work.input", message_id="M-1", channel="voice_dictation", provenance="observed",
        nature="command", modalities=["text", "image"],
        attachments=[{"asset_id": "A-1", "modality": "image"}, {"asset_id": "A-2", "modality": "image"}])
    add(j, "work.input", message_id="M-2", channel="typed", provenance="observed",
        nature="feedback", modalities=["text"])
    add(j, "work.input", message_id="M-3", channel="import_unknown", provenance="unknown",
        nature="narration", modalities=["text"])
    add(j, "work.output", response_id="R-1", reply_to_message_id="M-1")
    add(j, "work.output", response_id="R-2", reply_to_message_id="M-1")
    add(j, "work.output", response_id="R-3", reply_to_message_id="M-2")
    stats = summarize_work_journal(path, "W-01")
    assert stats["input_messages"] == 3
    assert stats["assistant_outputs"] == 3
    assert stats["responded_inputs"] == 2
    assert stats["channels_observed"] == {"voice_dictation": 1, "typed": 1}
    assert stats["channels_unverified"] == {"import_unknown": 1}
    assert stats["messages_with_modality"] == {"text": 3, "image": 1}
    assert stats["attached_assets"] == {"image": 2}


def test_finalization_requires_prior_approval_and_verification(tmp_path):
    path = tmp_path / "river.jsonl"
    j = EvidenceJournal(path)
    add(j, "work.finalized", deliverable_id="D-1")
    assert summarize_work_journal(path, "W-01")["finalized_deliverables"] == 0
    add(j, "work.verified", deliverable_id="D-1")
    add(j, "work.approved", deliverable_id="D-1")
    add(j, "work.finalized", deliverable_id="D-1")
    assert summarize_work_journal(path, "W-01")["finalized_deliverables"] == 1
    add(j, "work.reopened", deliverable_id="D-1")
    assert summarize_work_journal(path, "W-01")["finalized_deliverables"] == 0


def test_no_raw_text_or_claimed_voice_origin(tmp_path):
    j = EvidenceJournal(tmp_path / "river.jsonl")
    with pytest.raises(ValueError, match="RAW_CONTENT_FORBIDDEN"):
        add(j, "work.input", message_id="M-1", channel="typed", provenance="observed",
            nature="command", modalities=["text"], raw_text="secret material")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORIGIN_CLAIM"):
        add(j, "work.input", message_id="M-2", channel="voice_live", provenance="unknown",
            nature="narration", modalities=["text"])


def test_tamper_blocks_statistics(tmp_path):
    path = tmp_path / "river.jsonl"
    j = EvidenceJournal(path)
    add(j, "work.input", message_id="M-1", channel="typed", provenance="observed",
        nature="command", modalities=["text"])
    content = path.read_text().replace('"typed"', '"voice_live"')
    path.write_text(content)
    with pytest.raises(ValueError, match="EVIDENCE_CHAIN_INVALID"):
        summarize_work_journal(path, "W-01")


def test_distinct_workstreams_do_not_mix(tmp_path):
    path = tmp_path / "river.jsonl"
    j = EvidenceJournal(path)
    add(j, "work.tool", tool_call_id="TOOL-1")
    append_work_event(j, kind="work.tool", payload={"work_id":"W-02", "tool_call_id":"TOOL-2"},
        station_id="GES-ALPHA-001", principal_id="DM-001", session_id="SES-001",
        correlation_id="COR-002", source="test")
    assert summarize_work_journal(path, "W-01")["tool_invocations"] == 1
    assert summarize_work_journal(path, "W-02")["tool_invocations"] == 1
