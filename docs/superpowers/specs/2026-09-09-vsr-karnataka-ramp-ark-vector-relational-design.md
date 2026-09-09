# VSR Karnataka RAMP ARK — Vector + Relational Design R0.3

## Status
Approved architecture baseline from the September 9, 2026 VSR India Door/Accelerator and Karnataka RAMP design sequence. This document defines the first persistent opportunity-graph slice for `ARK-VSR-IN-KA-001`.

## Repository Role
`genesis-ark` remains the root orchestration repository for Genesis/VSR. This design adds registry, relationship, eligibility, provenance, semantic-retrieval, Warden-decision, and River-evidence contracts. It does not move authority into a front-end, a vector database, or an external programme.

## Objective
Create a governed Karnataka Opportunity ARK that can:

1. register VSR objects and external programme references;
2. represent RAMP Karnataka as an external programme, not a VSR-owned service;
3. bind `BNR-KA-DOD-001` as the first regional execution node;
4. persist Doors, Accelerators, Capabilities, Requirements, Providers, Estates, and Outcomes relationally;
5. use vector retrieval to discover semantically relevant programmes/capabilities/documents;
6. evaluate eligibility deterministically from evidence-backed facts and rules;
7. route authorized actions through Warden;
8. produce River receipts for material activation and outcome events.

The R0.3 substrate is PostgreSQL with `pgvector`. A separate graph database or vector database is intentionally deferred.

## Canonical Identity

```text
ARK-VSR-IN-KA-001
VSR Karnataka Opportunity ARK
```

Primary pilot geography:

```text
India
  -> Karnataka
    -> Bengaluru Rural
      -> Doddaballapura
        -> BNR-KA-DOD-001
```

Primary external programme binding:

```text
PROGRAM-IN-MSME-RAMP-KA
```

## Non-Ownership Boundary
RAMP Karnataka is an external public programme. Registration inside the ARK means VSR has discovered and modelled the programme from authoritative sources. It does not imply partnership, endorsement, delegated government authority, application approval, or commercial rights.

Canonical relationship:

```text
ARK-VSR-IN-KA-001
  -[EXTERNAL_PROGRAM_LINK]-> PROGRAM-IN-MSME-RAMP-KA
```

The relationship carries provenance, effective dates, source authority, verification state, and supersession metadata.

## Design Choice

### A. PostgreSQL + pgvector — Selected
One transactional substrate holds relational truth, graph-style edges, JSONB policy detail, provenance, and vector embeddings.

Advantages:
- one consistency boundary;
- SQL joins remain authoritative;
- pgvector supports semantic retrieval without a second datastore;
- mature backup/replication tooling;
- straightforward integration with existing Alpha PostgreSQL operations;
- easy future extraction of specialised search/graph services if scale demands it.

### B. PostgreSQL + dedicated vector database — Deferred
Potentially useful for very large embedding corpora or specialised ANN workloads, but it introduces dual-write, deletion, lineage, and synchronization complexity before the opportunity schema stabilises.

### C. PostgreSQL + graph DB + vector DB — Deferred
Useful for highly connected multi-hop analysis at larger scale, but premature for the first Karnataka ARK. R0.3 uses an explicit edge table and recursive SQL for graph traversal.

## Core Invariant

> Vectors nominate candidates. Relational rules determine truth. Warden determines authority. River proves execution.

No vector similarity score may directly establish eligibility, entitlement, provider approval, legal status, programme availability, or authorization.

## Domain Model

### Registry Objects
All first-class objects use a shared registry identity:

- `ARK`
- `PROGRAM`
- `DOOR`
- `ACCELERATOR`
- `CAPABILITY`
- `REQUIREMENT`
- `PROVIDER`
- `ESTATE`
- `PRINCIPAL`
- `BNR`
- `GEOGRAPHY`
- `OUTCOME`
- `SOURCE`

Each object has one canonical `object_id`, `object_type`, lifecycle state, authority owner, geography, version/effective dates, provenance, and extensible attributes.

### Object Edges
Relationships are first-class records rather than embedded arrays.

Initial edge vocabulary:

- `EXTERNAL_PROGRAM_LINK`
- `OFFERS`
- `REQUIRES`
- `SATISFIES`
- `FULFILLS`
- `LOCATED_IN`
- `ELIGIBLE_IN`
- `PROVIDED_BY`
- `SEEKS`
- `UNLOCKS`
- `SUPERSEDES`
- `EVIDENCED_BY`
- `GOVERNED_BY`

Edges are directed, versioned, provenance-bearing, and can carry conditions and weights.

## RAMP Karnataka Seed

`PROGRAM-IN-MSME-RAMP-KA` initially links to accelerator/capability families derived from the verified RAMP Karnataka programme record:

```text
PROGRAM-IN-MSME-RAMP-KA
  -> ACC-RAMP-ZED
  -> ACC-RAMP-LEAN
  -> ACC-RAMP-TECH-CLINIC
  -> ACC-RAMP-DPR
  -> ACC-RAMP-FUNDING
  -> ACC-RAMP-EXPORT
  -> ACC-RAMP-TREDS
  -> ACC-RAMP-SKILLING
  -> ACC-RAMP-BUSINESS-FACILITATION
```

These identifiers are registry objects. Their current availability and exact eligibility remain source- and rule-version dependent.

## Relational Schema

### `arks`
Stores ARK identity and governance root.

Minimum fields:

```text
ark_id PK
name
jurisdiction
state
registry_namespace
warden_namespace
river_namespace
created_at
effective_from
effective_until
```

### `registry_objects`
Canonical object registry.

```text
object_id PK
ark_id FK
object_type
name
state
authority_owner
geography_id FK nullable
attributes JSONB
version
valid_from
valid_until
supersedes_object_id nullable
created_at
updated_at
```

### `object_edges`
Typed graph relation table.

```text
edge_id PK
ark_id FK
from_object_id FK
edge_type
to_object_id FK
weight numeric nullable
conditions JSONB
source_id FK nullable
valid_from
valid_until
supersedes_edge_id nullable
created_at
```

Uniqueness is enforced over active edge identity where appropriate. Historical edges remain immutable and are superseded rather than silently edited.

### `estate_facts`
Evidence-backed facts used by eligibility evaluation.

```text
fact_id PK
estate_id FK
fact_type
value_json JSONB
evidence_id nullable
verification_state
verified_at
valid_from
valid_until
source_id nullable
```

Examples: Udyam class, turnover band, investment, sector, location, registrations, certifications, energy profile, export status, workforce capacity.

### `eligibility_rules`
Deterministic eligibility predicates.

```text
rule_id PK
target_object_id FK
rule_version
predicate_json JSONB
required_evidence JSONB
result_if_true
result_if_false
source_id FK
effective_from
effective_until
state
```

Rule evaluation returns structured states such as:

```text
ELIGIBLE
CONDITIONAL
INELIGIBLE
UNKNOWN
SOURCE_STALE
```

`UNKNOWN` is mandatory when required facts are missing. The engine must not convert missing evidence into a negative fact.

### `providers`
Provider-specific execution metadata.

```text
provider_id PK
registry_object_id FK
provider_state
credential_state
geography_id FK nullable
attributes JSONB
```

A provider is never treated as approved merely because semantic search found it.

### `provider_capabilities`
Many-to-many provider/capability binding.

```text
provider_id FK
capability_object_id FK
state
verification_source_id FK nullable
valid_from
valid_until
PRIMARY KEY(provider_id, capability_object_id, valid_from)
```

### `opportunities`
Materialized compiler output for an Estate/Principal and target outcome.

```text
opportunity_id PK
ark_id FK
estate_id FK nullable
principal_id FK nullable
outcome_object_id FK
target_object_id FK
eligibility_state
opportunity_score numeric
missing_requirements JSONB
compiler_version
calculated_at
expires_at
```

Opportunity records are recomputable snapshots, not eternal truth.

### `warden_decisions`
Immutable authorization decisions.

```text
decision_id PK
ark_id FK
principal_id
session_id
action
target_object_id
result
policy_id
conditions JSONB
obligations JSONB
reason_code
decided_at
valid_until
supersedes_decision_id nullable
```

### `river_receipts`
Evidence references for material events.

```text
receipt_id PK
ark_id FK
decision_id FK nullable
object_id FK nullable
event_type
payload_hash
correlation_id
causation_id
occurred_at
receipt_uri nullable
classification
```

## Knowledge and Vector Schema

### `knowledge_documents`
Stores source-document identity and provenance, not necessarily the entire original binary.

```text
document_id PK
ark_id FK
source_type
source_uri
authority_owner
published_at
effective_from
effective_until
retrieved_at
content_hash
verification_state
metadata JSONB
```

### `knowledge_chunks`
Searchable document chunks.

```text
chunk_id PK
document_id FK
ordinal
content
content_hash
embedding vector(N)
embedding_model
embedding_version
metadata JSONB
```

### `object_embeddings`
Semantic representation of registry objects.

```text
object_id FK
embedding_type
embedding vector(N)
embedding_model
embedding_version
derived_from_hash
created_at
PRIMARY KEY(object_id, embedding_type, embedding_version)
```

Embedding dimension `N` is migration-configured and must match the selected model. It is not hard-coded into domain contracts.

## Source Ingestion
R0.3 uses versioned source ingestion rather than assuming an official RAMP transactional API.

Pipeline:

```text
authoritative source
  -> fetch/snapshot
  -> hash + provenance record
  -> extract programme facts
  -> chunk text
  -> create/update registry candidates
  -> embed chunks/objects
  -> human/policy verification where required
  -> activate relational rules/edges
```

A changed source never silently mutates historical truth. New source snapshots and superseding object/rule versions are created.

## Opportunity Compiler

Input:
- ARK;
- Estate or Principal;
- geography;
- desired Outcome or natural-language need;
- current evidence-backed facts.

Execution:

```text
1. semantic retrieval
2. ARK/geography/lifecycle filtering
3. relational graph expansion
4. deterministic eligibility evaluation
5. missing-requirement derivation
6. BNR/provider matching
7. opportunity scoring
8. Warden authorization when an action crosses an authority boundary
9. River receipt when activation/submission/execution occurs
```

### Semantic Retrieval
Vector search may retrieve:
- accelerators;
- programmes;
- capabilities;
- source chunks;
- similar past requirements.

Its output is a candidate set only.

### Relational Filtering
Candidates must then satisfy:
- ARK linkage;
- active lifecycle state;
- geography;
- programme validity;
- explicit relational bindings;
- required authority/provenance thresholds.

### Eligibility Evaluation
Rules operate only on structured facts and verified source versions. Results include a fact/rule trace so an operator can explain exactly why an opportunity is open, conditional, locked, or unknown.

### Missing-Requirement Graph
If a candidate is conditional, each unsatisfied requirement becomes a graph node. The compiler recursively resolves capabilities and local providers that can satisfy it.

Example:

```text
ACC-RAMP-FUNDING
  -> REQUIRES -> CAP-DPR
  -> FULFILLED_BY -> BNR provider candidate
```

## BNR-KA-DOD-001
The first BNR is a regional execution node, not a blanket authority grant.

Initial capability classes:
- business facilitation;
- DPR/project development;
- technical consultancy;
- technology clinic;
- ZED/LEAN support;
- funding facilitation;
- TReDS facilitation;
- export/market access;
- skilling/workforce;
- environmental and social management.

Providers attached to these classes have independent verification and lifecycle states.

## Warden Boundary
Warden is required before any action that:
- shares protected Estate/Principal data externally;
- submits an application;
- accepts programme/provider terms;
- initiates financial/regulated activity;
- creates a binding service order;
- authorizes a third party to act;
- causes settlement or material external effect.

Search, public-source indexing, deterministic eligibility calculation from already-authorized facts, and read-only opportunity ranking do not themselves imply external authorization.

Policy posture remains deny-by-default for external effects.

## River Evidence
Material events requiring receipts include:
- source verification/supersession;
- eligibility calculation used for an action;
- Warden decision;
- external submission initiation;
- provider engagement;
- acknowledgement/sanction/denial received;
- activation;
- completion;
- measurable outcome.

River stores evidence of what happened. It does not rewrite external programme records to fit VSR expectations.

## Security and Data Governance Invariants
1. Vector similarity never grants entitlement or authority.
2. External programme registration never implies partnership.
3. Missing evidence produces `UNKNOWN` or `CONDITIONAL`, not fabricated certainty.
4. Every active eligibility rule has a source and effective period.
5. Historical rule/object versions are superseded, not destructively rewritten.
6. Sensitive raw documents need not be embedded; use approved redacted/derived text where policy requires.
7. Embeddings inherit the classification of their source content.
8. Cross-authority data sharing requires Warden approval and purpose limitation.
9. River receipts contain hashes/references and necessary metadata, not secrets by default.
10. Provider discovery and provider approval are separate states.
11. Financial facilitation does not make VSR a lender, exchange, or regulated intermediary unless separately authorized and licensed.
12. Government/public programme discovery does not make VSR a government submission authority unless explicitly integrated and authorized.

## Error and Staleness Handling
The system distinguishes:
- source fetch failure;
- source stale/expired;
- extraction failure;
- embedding failure;
- vector index unavailable;
- relational integrity failure;
- missing Estate facts;
- ambiguous eligibility;
- Warden denial/unavailable;
- River evidence failure.

Read-only relational eligibility remains available if vector search is unavailable. External mutations fail closed when Warden or mandatory River evidence is unavailable.

## Indexing Strategy
Initial PostgreSQL indexes:
- B-tree: IDs, lifecycle state, object type, geography, effective dates;
- GIN: selected JSONB attributes/conditions;
- composite: active edge traversal keys;
- pgvector ANN index on `knowledge_chunks.embedding` and later `object_embeddings.embedding` once corpus size justifies it.

R0.3 should begin with exact vector search for small seed corpora and add HNSW/IVFFlat only after measurement. Index choice is an implementation concern, not a registry contract.

## API Boundaries
Implementation should expose narrow services/contracts:

- `RegistryService` — object/edge resolution and lifecycle queries;
- `SourceService` — source snapshots/provenance;
- `SemanticRetriever` — candidate IDs with scores and provenance;
- `EligibilityEngine` — deterministic decision trace;
- `OpportunityCompiler` — combines retrieval, graph, rules, gaps, score;
- `ProviderMatcher` — capability/geography/provider matching;
- `WardenClient` — authorization boundary;
- `RiverClient` — receipt/evidence boundary.

Consumers must not query vector tables directly to infer authority.

## Initial File/Module Shape
Proposed implementation slice inside `genesis-ark`:

```text
opportunity-ark/
  db/
    migrations/
    seeds/
  contracts/
  registry/
  sources/
  semantic/
  eligibility/
  compiler/
  providers/
  warden/
  river/
  tests/
  README.md
```

The existing Alpha control plane remains separate under `control-plane/`. Shared Warden/River contracts should be referenced rather than duplicated where compatible.

## Seed Migration
The existing `VSR India Opportunity Graph R0.2` seed maps into R0.3 as follows:

- Doddaballapura geography -> `GEOGRAPHY` object;
- Karnataka SWS -> `DOOR` object;
- Karnataka Industrial Policy benefits -> `ACCELERATOR` objects + eligibility rules;
- Udyam -> `DOOR` plus Estate facts/evidence;
- RAMP Karnataka -> `PROGRAM` + `EXTERNAL_PROGRAM_LINK` + offered accelerator/capability edges;
- IndiaAI -> `DOOR`/`ACCELERATOR` objects;
- ONDC -> `DOOR` with role/maturity metadata;
- BNR DPR and related capabilities -> `CAPABILITY` objects bound to `BNR-KA-DOD-001`.

The migration must preserve all R0.2 source URLs and verification states.

## Testing Strategy

### Schema tests
- foreign keys and enum/check constraints;
- active lifecycle queries;
- edge supersession;
- vector dimension/model metadata consistency.

### Registry tests
- known IDs resolve;
- unknown IDs fail explicitly;
- external programme does not appear as VSR-owned;
- superseded versions remain queryable historically.

### Eligibility tests
- verified qualifying facts -> `ELIGIBLE`;
- missing mandatory facts -> `UNKNOWN` or `CONDITIONAL`;
- explicit non-qualifying facts -> `INELIGIBLE`;
- expired rule/source -> `SOURCE_STALE`;
- vector score cannot alter rule result.

### Semantic tests
- relevant need retrieves RAMP capability candidates;
- unrelated candidates remain below configured threshold;
- semantic outage does not corrupt relational truth.

### Opportunity compiler tests
- natural-language need -> candidate -> rule trace -> missing requirements;
- Doddaballapura geography filters correctly;
- missing DPR can resolve to a DPR capability/provider path;
- score is reproducible from versioned inputs.

### Warden/River tests
- read-only search does not create false external authority;
- external submission without Warden permit is rejected;
- permitted activation emits required River receipt;
- Warden or mandatory evidence outage fails external mutation closed.

## Acceptance Criteria
R0.3 design is implementable when:
- `ARK-VSR-IN-KA-001` is uniquely registered;
- RAMP Karnataka is represented as an external programme with provenance;
- PostgreSQL + pgvector is the only required database substrate;
- all core object types and typed edges are persistable;
- eligibility is deterministic and evidence-backed;
- semantic search is candidate generation only;
- missing requirements can form a recursive unlock path;
- `BNR-KA-DOD-001` can advertise capabilities without granting providers blanket approval;
- Warden gates material external effects;
- River can evidence the activation/outcome chain;
- R0.2 seed records can be migrated without loss of source provenance.

## Explicitly Deferred
- dedicated graph database;
- dedicated vector database;
- autonomous submission to RAMP or government portals;
- scraping behind authentication or access controls;
- automatic financial transactions;
- provider procurement/contracting automation;
- national-scale multi-ARK federation;
- real-time programme monitoring;
- public production UI;
- SILK settlement implementation beyond references to future settlement events.

These are additive future slices and must not change the R0.3 core invariant.

## Rollout Order
1. database extension/migrations;
2. canonical ARK and object registry;
3. R0.2 seed import;
4. typed edges and source provenance;
5. eligibility engine;
6. document/chunk ingestion;
7. embeddings and semantic retrieval;
8. opportunity compiler;
9. BNR/provider matching;
10. Warden/River integration;
11. end-to-end Doddaballapura pilot acceptance.
