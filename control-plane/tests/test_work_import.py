import json
from zipfile import ZipFile

import pytest

from genesis_control_plane.work_import import compile_events, import_export, load_export, main
from genesis_control_plane.work_evidence import summarize_work_journal


def conversation():
    return {
        "id": "CONV-1", "title": "Private client info do not log",
        "mapping": {
            "root": {"id": "root", "message": None, "parent": None},
            "user1": {"id": "user1", "parent": "root", "message": {
                "id": "M-1", "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["Top secret prompt", {"content_type": "image_asset_pointer", "asset_pointer": "private://secret.jpg"}]},
                "metadata": {"attachments": [{"name": "project.pdf", "id": "private-file-123", "mime_type": "application/pdf"}]}
            }},
            "answer": {"id": "answer", "parent": "user1", "message": {
                "id": "A-1", "author": {"role": "assistant"}, "recipient": "all", "content": {"content_type": "text", "parts": ["Secret answer"]}}},
            "hidden": {"id": "hidden", "parent": "answer", "message": {
                "id": "A-2", "author": {"role": "assistant"}, "recipient": "to=python", "content": {"content_type": "text", "parts": ["execute private"]}}},
            "branch": {"id": "branch", "parent": "answer", "message": {
                "id": "M-2", "author": {"role": "user"}, "content": {"content_type": "text", "parts": ["More private words"]}}},
            "answer2": {"id": "answer2", "parent": "branch", "message": {
                "id": "A-3", "author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["other"]}}}
        }
    }


def test_source_export_counts_unknown_origin_and_no_secrets(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps([conversation()]))
    journal = tmp_path / "river.jsonl"
    preview = import_export(p, journal_path=journal, principal_id="DM-ALPHA")
    assert preview["mode"] == "preview"
    assert not journal.exists()
    assert preview["user_messages"] == 2
    assert preview["assistant_outputs"] == 2
    assert preview["unknown_origin_user_messages"] == 2
    assert preview["attached_assets"] == {"image": 1, "file": 1}
    assert preview["messages_with_modality"] == {"text": 2, "image": 1, "file": 1}
    assert preview["responded_input_messages"] == 2
    committed = import_export(p, journal_path=journal, principal_id="DM-ALPHA", commit=True)
    assert committed["new_events"] == 4
    data = journal.read_text()
    for private in ["Top secret prompt", "Secret answer", "project.pdf", "private-file-123", "CONV-1", "private://secret", "Private client"]:
        assert private not in data
    events, _ = compile_events([conversation()])
    work_id = events[0][1]["work_id"]
    stats = summarize_work_journal(journal, work_id)
    assert stats["input_messages"] == 2
    assert stats["assistant_outputs"] == 2
    assert stats["responded_inputs"] == 2
    assert stats["channels_observed"] == {}
    assert stats["channels_unverified"] == {"import_unknown": 2}
    assert stats["attached_assets"]["image"] == 1
    assert stats["attached_assets"]["file"] == 1
    again = import_export(p, journal_path=journal, principal_id="DM-ALPHA", commit=True)
    assert again["new_events"] == 0 and again["already_recorded"] == 4


def test_numbered_json_and_zip_supported(tmp_path):
    p = tmp_path / "export.zip"
    with ZipFile(p, "w") as z:
        z.writestr("some/folder/conversations-0001.json", json.dumps([conversation()]))
        z.writestr("other/note.txt", "private info")
    assert len(load_export(p)) == 1
    assert import_export(p, journal_path=tmp_path / "j.jsonl", principal_id="DM-1")["messages_identified"] == 4


def test_export_invalid_shape_rejected(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text('{"arbitrary":"text"}')
    with pytest.raises(ValueError, match="EXPECTED_CONVERSATIONS_ARRAY"):
        load_export(p)


def test_tampered_journal_prevents_reimport(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps([conversation()]))
    jp = tmp_path / "river.jsonl"
    import_export(p, journal_path=jp, principal_id="DM-1", commit=True)
    jp.write_text(jp.read_text().replace("chatgpt_export", "fake_export", 1))
    with pytest.raises(ValueError, match="EVIDENCE_CHAIN_INVALID"):
        import_export(p, journal_path=jp, principal_id="DM-1", commit=True)


def test_cli_default_preview(tmp_path, capsys):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps([conversation()]))
    jp = tmp_path / "river.jsonl"
    assert main(["--export", str(p), "--journal", str(jp), "--principal-id", "DM-1"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["new_events"] == 4 and output["mode"] == "preview"
    assert not jp.exists()


def test_historical_timestamp_and_missing_id():
    data = conversation()
    data["mapping"]["user1"]["message"]["create_time"] = 1780000000.0
    events, missing = compile_events([data, {"mapping": {}}])
    assert missing["conversations_without_id"] == 1
    user = events[0][1]
    assert user["source_occurred_at"].startswith("2026-")
    assert all(p["channel"] == "import_unknown" for k,p in events if k == "work.input")
