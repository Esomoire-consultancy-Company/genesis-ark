# Genesis Work Evidence — R0.2 History Backfill and Source Capture

**Status:** draft PR, Alpha/local-library only. **No deployment or historical ChatGPT data import performed.**

This builds on GWIEP R0.1 and the existing Genesis hash-linked River JSONL evidence journal. The R0.2 source modules contain no network listener, no production Docker permissions, no automatic ChatGPT interception and no direct Warden approvals.

## A. Consent-based historical ChatGPT backfill

Supported inputs: a locally supplied conversation-export JSON array, or ZIP containing files named conversations.json / conversations-0001.json (etc). This is a best-effort parser for known mapping-node formats; other versions may require an adapter.

To PREVIEW a locally held export, from the control-plane directory:

    python -m genesis_control_plane.work_import \
      --export /path/to/conversations.json \
      --journal .runtime/work-evidence.jsonl \
      --principal-id DM-LOCAL-ALPHA

Nothing is appended unless the caller explicitly adds:

    --commit

The --principal-id is a caller-supplied label in R0.2, NOT an authenticated DigitalMe credential. Do not expose this import module to remote users. Restrict local filesystem access and perform any privacy review outside the importer before consenting to a commit.

### What it counts

- Distinct user messages and assistant message nodes from the export.
- Assistant-to-user message parentage following branch ancestry; tool-directed assistant nodes are excluded.
- Text, image, audio, video, or file modalities where recognizable.
- Attachment/asset occurrences, indexed by pseudonymous ID without storing name, link, transcript, image, or prompt.
- Missing source IDs, unavailable timestamps, unlinked outputs, messages with no content, mappingless conversations.
- Historical user input origin is ALWAYS import_unknown / unknown, never automatically typed or voice.
- Stable source IDs support replay and deduplication against an existing verified journal.

### Important evidence limitations

1. ChatGPT conversation exports may not identify keyboard input versus voice dictation. Absence is not evidence of a typed message.
2. An asset represented both as a content part and as metadata may be counted twice. Validate counts on samples before business use.
3. This prototype parses known source shapes, not every export schema or linked external file.
4. Source IDs are **pseudonymized with plain SHA-256, not irreversibly anonymized**. If source identifiers are guessable, correlation remains possible. For production, use tenant-keyed HMACs and secure key lifecycle management.
5. Messages on multiple branches are recorded; a user-facing "one chosen branch" view is not implemented.
6. Imported history records message/response provenance; it does **not** certify intent classification, execution, Docker mutation, Warden approval or actual deliverable completion.
7. No archive contents are extracted to disk; ZIP enumeration and uncompressed-size caps reduce, but do not eliminate, archive risks.
8. In the current JSONL implementation, appending many records revalidates and rereads the file repeatedly; large exports are not suitable for production ingestion as-is.

## B. Source-observed, signed future input

The module genesis_control_plane.work_capture provides two pure/library functions:

- sign_packet(packet, key): only a trusted client adapter holding a signing key may assert input-origin observations.
- accept_packet(journal, packet, key=..., expected_station_id=..., expected_principal_id=..., expected_source=...): verifies HMAC-SHA256 signature, 5-minute freshness, scope, event schema, capture_id, and best-effort single-process idempotency.

The verified source adapter supplies accurate channel provenance: typed / voice_dictation / voice_live / api. A signed claim demonstrates the configured adapter claimed to observe it, not independently that the device UI captured it correctly.

The library explicitly declines work.approved, work.verified, work.finalized and work.reopened events; authenticated Warden and relevant verification/acceptance proofs must handle these. The signing secret must be managed outside Git. Never log full packet content at a network edge.

### What the source packet looks like

    {
      "kind": "work.input",
      "payload": {
        "work_id": "GW-2026-001",
        "message_id": "M-100",
        "capture_id": "CAPTURE-100",
        "channel": "voice_dictation",
        "provenance": "observed",
        "nature": "command",
        "modalities": ["text", "image"],
        "attachments": [{"asset_id": "ASSET-100", "modality": "image"}]
      },
      "station_id": "GES-ALPHA-001",
      "principal_id": "DM-LOCAL-ALPHA",
      "session_id": "SESSION-100",
      "correlation_id": "CORR-100",
      "source": "approved_device",
      "issued_at": "2026-10-28T08:00:00+00:00"
    }

The adapter signs the above *unsigned* packet via sign_packet(), yielding a signature property. Work event payload keys are allowlisted in work_evidence.py.

## C. Retention, governance and deployment gates

- ChatGPT export is handled only after user-controlled export and opt-in.
- Metadata-only River events should be classified private, authorized per DigitalMe principal and purpose.
- A container's access to a tool does **not** prove the container is connected to the user's entire ChatGPT conversation history.
- No bypass of original chat privacy permissions.
- Do not infer source modality or user intent from writing style.
- Approval and versioned verification remain independent Warden-governed actions.
- Before any live API: a server-side identity/authority session, per-tenant key registry, replay persistence, rate limits, schema validation, sensitive-data redaction, idempotency uniqueness and adversarial tests are required.
- Before multiple writers: transactional persistence, concurrent append locks, durability, backups and independent anchored checkpoints.
- Before production import: large-data streaming/batching, content-type schema compatibility tests, size limits and operation dry-runs at scale.
- Before dashboard truth claims: reconcile work IDs across conversations, evidence gaps, unrelated assistant messages, interrupted work and tool execution receipts; preserve LBM and OCM state.
- Preview should display completeness and unknown-origin counts as first-class values; zero and unknown must never be conflated.

## Tests

From the control-plane root:

    python -m pytest tests/test_work_evidence.py tests/test_work_import.py tests/test_work_capture.py -q

Local isolated prototype run on 2026-10-28: 16 focused tests passed. Full repository, container, deployment, integration and live ChatGPT tests remain unverified.

**Next interface:** a local, consent-gated source selection and import preview UI (not added here), then authenticated workstream reconciliation and dashboard aggregates (pending).
