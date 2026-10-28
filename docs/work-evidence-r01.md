# Genesis Work Intelligence & Evidence Protocol (GWIEP) R0.1

**Status:** pilot contract; additive to the existing GES-ALPHA River JSONL journal. **Not deployed.**

## Why

Unify narrated, typed, visual, file-based and tool-driven work without confusing a human instruction with executed work. Scope is one DigitalMe principal and named workstream initially; multiple conversations may link to the same `work_id`. River holds event evidence, Warden governs authority, Synnergyze executes guarded skills/tools, Genesis assigns workflow IDs, and LBM/OCM are persistent improvement controls.

## Counting dimensions

These are independent axes; never sum overlapping categories as if mutually exclusive:

| Dimension | R0.1 field | Counting rule |
| --- | --- | --- |
| Message origin | `channel` | one user input per unique `message_id`, channel: `typed`, `voice_dictation`, `voice_live`, `api`, `import_unknown` |
| Origin certainty | `provenance` | `observed` only if supplied by trustworthy capture surface; `inferred` or `unknown` must not be claimed confirmed |
| Modality present | `modalities` | one message may increment text + image simultaneously; `messages_with_modality` is overlap-inclusive |
| Attachments | `attachments` | each unique `asset_id` per message contributes one item of its specified modality |
| Intent kind | `nature` | `narration`, `command`, `question`, `feedback`, `evidence`, `other`; orthogonal to channel |
| Outputs | `response_id` | each unique assistant output counted once; streaming chunks must share one response ID |
| Responded inputs | `reply_to_message_id` | number of unique input IDs referenced by output events |
| Tool attempts | `tool_call_id` | number of unique recorded tool invocations, not successful actions |
| Revisions | `revision_id` | number of separately identified revision requests |
| Verification | `deliverable_id` | distinct deliverables with a recorded verification event; not independently guaranteed without receipt authority |
| Acceptance | `deliverable_id` | distinct deliverables with an approval event |
| Finalization | `deliverable_id` | finalized event after linked verification + approval, with no subsequent reopening |

**Do not equate** an AI answer, code generated, tool request, tool success, deployed change, verified result and accepted deliverable. They have different states and proof requirements. `finalized_deliverables` is a *provisional event-order count* until Warden authenticates the parties and receipts.

## Event model

Existing `EvidenceEvent` remains unchanged. Every new work-event uses existing `EvidenceJournal.append`, the same hash chaining, existing `principal_id`, `session_id`, `station_id`, `correlation_id`, and `causation_id`. Its `subject` is the stable `work_id`.

The R0.1 event types are:

- `work.input` — user message and optional asset metadata, with explicit channel and certainty;
- `work.output` — assistant answer/artefact and optional originating `message_id`;
- `work.tool` — one tool invocation, whether it succeeded or failed;
- `work.revision` — a revision request, linking the earlier version;
- `work.verified` — external verification evidence required before acceptance;
- `work.approved` — explicit named acceptance;
- `work.finalized` — finalization declared only after verification and approval events;
- `work.reopened` — subsequent modification invalidates the finalized state.

Example privacy-minimized input event payload:

```json
{
  "work_id": "GW-2026-001",
  "message_id": "M-001",
  "channel": "voice_dictation",
  "provenance": "observed",
  "nature": "command",
  "modalities": ["text", "image"],
  "attachments": [{"asset_id": "A-001", "modality": "image"}]
}
```

**Mandatory:** source adapters must keep raw content, images, credentials, transcripts and privately identifying details out of the operational metadata journal. Use content stores with separate consent/retention policy if the content itself is necessary. This metadata-only implementation is a prototype; do not ingest untrusted payloads without schema allowlisting, authn/authz and access controls.

## Workflow and protocol persistence

```txt
Source (ChatGPT export / authorized client / app / MCP / Docker / GitHub)
 -> Source adapter + observed provenance or unknown classification
 -> Genesis Work Intent Compiler (stable work_id; input/intent/work decomposition)
 -> Warden decision / capability token for *mutations*
 -> Synnergyze MCP authorized tool calls and executable workflow
 -> verification tied to actual resources
 -> River evidence events and reconciliation
 -> LBM: learn / build / maintain; OCM: observe / correct / maintain
 -> final approval, versioned publication or reopen/repair
```

On each task, track intent, performed action, observed result and next maintenance obligation. Changes must not silently replace prior evidence.

## Historic counts versus ongoing counts

1. **Backfill:** ingest a user-authorized export or prior logs; preserve source record IDs and times, deduplicate imports and classify origin as `import_unknown` absent explicit input metadata. The ChatGPT export may show text and attachments but cannot be assumed to distinguish keyboard entry from speech dictation. Mark completeness and missingness.
2. **Live telemetry:** use an authorized source/client that knows capture modality, creates stable IDs, and emits agreed event types. A Docker container cannot automatically inspect private ChatGPT input methods merely because a tool/session interacted with it.
3. **Execution proof:** link GitHub commit/PR/test run IDs, Docker resource IDs, CI build IDs, Warden decision/WEG verification and River receipt IDs. Require explicit approvals for finalized deliverables.
4. **Aggregation:** initially use `summarize_work_journal(path, work_id)`; when data volume rises, move to transactional storage and periodic materialized reports. JSONL on a single host is not a distributed ledger.

## Acceptance / controls needed before deployment

- Instrument an explicit source adapter with permission; deny silent interception.
- Enforce event payload allowlist, schema versioning, row-level DigitalMe tenancy authorization and retention.
- Add stable event ID/idempotency keys and duplicate-preventing transactional storage.
- Make concurrent append safe; journal currently reads and verifies the entire chain on each write.
- Provide fsync/backup/recovery and independent checkpoints: hash chaining alone does not stop full-file substitution.
- Validate Warden-issued approval and verification references; mere strings are not proof.
- Attribute tool failures, costs/usage, elapsed times, revision loops and task boundaries separately.
- Reopen a deliverable on later changes, and require new verification and approval for the revised version.
- Reconcile incomplete outputs, skipped steps, and interrupted sessions.
- Test with the Alpha station; do not connect production Docker or ChatGPT history as part of this PR.

## Initial view labels

**Work received | Recorded inputs | Spoken | Dictated | Typed | Images | Files | Assistant outputs | Tool attempts | Revisions | Verified | Approved | Finalized | Reopened | Unknown origin | Missing evidence.**

Counts apply by workstream, member, node, period and version. Unknown must be shown, not silently converted to zero.
