# Genesis Engineering Station Alpha Control Plane — Design R0.1

## Status
Approved architecture baseline from the September 9, 2026 Genesis/Warden/GES design sequence. This document narrows that architecture to the first deployable Alpha slice.

## Repository Role
`genesis-ark` is the root orchestration repository for Genesis/VSR. It owns the control-plane contracts, policy bundles, deployment descriptors, and cross-system references. UI-specific implementation remains outside this repository.

## Objective
Stand up the smallest end-to-end governed execution path for `GES-ALPHA-001` / `ALPHA-NODE-001`:

1. identify a registered resource;
2. request one registered capability;
3. evaluate it through Warden;
4. issue a short-lived one-shot capability token;
5. validate the token at the Warden Execution Gateway (WEG);
6. execute one bounded Docker operation;
7. verify the result;
8. emit a River evidence receipt.

The first governed mutation is `container.instance.restart` against a single Alpha container. No production, raw-root-shell, credential reveal, or physical-control authority is included in R0.1.

## Design Choice
Three deployment shapes were considered.

### A. Add the control plane to the VSR front-end repository
Rejected. The VSR repository is a V0/Vercel application and auto-syncs from V0, so it should consume control-plane state rather than own authoritative governance code.

### B. Create another standalone repository
Deferred. A separate repo may become useful when Warden/WEG need independent release lifecycles, but creating another authority surface before the contracts are stable would fragment Alpha.

### C. Anchor contracts and deployment descriptors in `genesis-ark`
Selected. This keeps Genesis-level authority artifacts in the root orchestration repository while allowing runtime services to be deployed independently later.

## R0.1 Components

### 1. Genesis Registry Slice
Provides canonical Alpha records for:
- estate: `GENESIS-ESTATE-001`;
- station: `GES-ALPHA-001`;
- node: `ALPHA-NODE-001`;
- Docker adapter: `GEN-ADAPTER-DOCKER-001`;
- one target container resource;
- capability: `container.instance.restart`.

R0.1 may use static YAML/JSON fixtures checked into the repository. PostgreSQL-backed registry mutation is intentionally deferred.

### 2. Warden Decision Service
Input: canonical command envelope.

Output:
- `PERMIT` or `DENY`;
- matched policy version;
- conditions/obligations;
- decision identifier;
- expiry.

Initial rule:
- principal/session known;
- environment must be `alpha`;
- station must be `GES-ALPHA-001`;
- capability must be exactly `container.instance.restart`;
- target must be explicitly registered;
- evidence must be enabled;
- risk must not exceed the R0.1 threshold.

Policy posture is deny-by-default.

### 3. Capability Token Issuer
After a Warden `PERMIT`, issue a one-shot signed token bound to:
- command ID;
- decision ID;
- principal ID;
- session ID;
- station ID;
- adapter ID;
- target resource ID;
- capability name;
- canonical parameter hash;
- audience;
- issue/not-before/expiry timestamps;
- nonce;
- maximum use count of one.

R0.1 signing may use HMAC-SHA256 with a local development key supplied at runtime. The key must never be committed.

### 4. Warden Execution Gateway
WEG is the enforcement boundary. It validates:
1. token signature;
2. audience;
3. expiry/not-before;
4. revocation/consumption state;
5. station/session/principal binding;
6. adapter binding;
7. target binding;
8. capability binding;
9. parameter hash;
10. evidence-channel readiness.

Only after all checks pass may WEG dispatch to an adapter.

### 5. Docker Adapter
R0.1 adapter surface:
- `container.instance.list` — read-only support;
- `container.instance.inspect` — read-only support;
- `container.logs.read` — read-only support;
- `container.instance.restart` — first governed mutation.

The adapter translates the canonical capability into Docker-specific execution. It must not expose arbitrary `exec(any_string)` as part of the governed R0.1 surface.

### 6. Verification
After restart, verification checks:
- target container exists;
- container is running;
- Docker health is healthy when a healthcheck is defined;
- execution corresponds to the authorized target.

A successful Docker CLI exit code alone is not sufficient for `VERIFIED`.

### 7. River Evidence Sink
R0.1 evidence may be an append-only local JSONL journal plus structured receipt files until the existing RiverOS API contract is available in the repository.

Required chain:
- observation/request;
- command;
- Warden decision;
- capability token metadata, excluding secrets/signing key;
- execution result;
- verification result;
- final receipt hash.

Each record carries correlation and causation identifiers.

## Canonical Flow

```text
DigitalMe / operator
        |
        v
Command envelope
        |
        v
Warden decision
        |
        v
One-shot capability token
        |
        v
WEG validation
        |
        v
Docker adapter
        |
        v
Target container
        |
        v
Verification
        |
        v
River evidence receipt
```

## Command Contract
Minimum fields:

```yaml
command_id:
correlation_id:
principal_id:
session_id:
station_id: GES-ALPHA-001
adapter_id: GEN-ADAPTER-DOCKER-001
target_resource_id:
capability: container.instance.restart
parameters:
risk_class:
requested_at:
expires_at:
```

## Decision Contract

```yaml
decision_id:
command_id:
result: PERMIT | DENY
policy_id: WARDEN-ENGINEERING-R0.1
conditions: []
obligations: []
decided_at:
valid_until:
reason_code:
```

Decisions are immutable. A later decision supersedes rather than edits an earlier one.

## Token Contract
Token metadata must include:

```yaml
token_id:
decision_id:
command_id:
principal_id:
session_id:
station_id:
adapter_id:
target_resource_id:
capability:
parameters_hash:
audience:
issued_at:
not_before:
expires_at:
max_uses: 1
nonce:
key_id:
```

## Evidence Contract
Each material event uses a common envelope:

```yaml
event_id:
event_type:
schema_version:
occurred_at:
station_id:
principal_id:
session_id:
source:
subject:
payload:
correlation_id:
causation_id:
classification:
```

## Runtime Boundaries
R0.1 is Alpha-only.

Allowed:
- local registered Docker engine;
- explicit registered test/Alpha containers;
- read-only discovery/inspection;
- one governed restart capability.

Denied by design:
- production targets;
- wildcard resources;
- root/Administrator arbitrary shell;
- destructive database operations;
- network/firewall mutation;
- secret reveal;
- physical/serial/BLE writes;
- cross-node authority;
- long-lived privileged tokens.

## Failure Handling
The system must distinguish:
- authorization failure;
- token validation failure;
- preflight failure;
- dispatch failure;
- execution failure;
- verification failure;
- evidence failure.

A failure never widens authority. If Warden, WEG, registry resolution, or mandatory evidence is unavailable, governed mutation fails closed.

## Security Invariants
1. No privileged R0.1 effect without a named registered capability.
2. No governed action against an unnamed resource.
3. No capability token containing credentials or raw secrets.
4. Capability token is short-lived and one-shot.
5. Parameters are cryptographically bound to authorization.
6. Agent proposal does not equal authority.
7. Warden does not execute.
8. WEG does not invent policy.
9. Docker adapter refuses invalid or absent authority.
10. River evidence records result and verification, not secret material.

## Initial Files Planned
Implementation should keep units small and independently testable:

```text
control-plane/
  contracts/
  registry/
  warden/
  weg/
  adapters/docker/
  river/
  tests/
  README.md
```

Exact language/framework is selected during the implementation plan after checking the active Alpha runtime source tree. Existing local River services are not assumed to be present in this GitHub repository.

## Testing Strategy

### Contract tests
Validate command, decision, token, event, and receipt schemas.

### Warden tests
- registered Alpha restart -> permit;
- unknown capability -> deny;
- unknown target -> deny;
- wrong environment -> deny;
- risk above threshold -> deny or require approval as defined.

### WEG negative tests
- expired token -> reject;
- modified parameters -> reject;
- wrong target -> reject;
- wrong adapter -> reject;
- wrong audience -> reject;
- replayed token -> reject;
- unsigned/invalid signature -> reject.

### Adapter tests
Use a disposable test container. No tests may target production resources.

### End-to-end acceptance test
1. start disposable unhealthy/test container;
2. create restart command;
3. Warden permits;
4. token issued;
5. WEG validates;
6. Docker adapter restarts exactly that container;
7. verifier confirms expected state;
8. River receipt contains the full correlation chain;
9. reusing the same token is rejected.

## Deployment Maturity
Initial target: `E2 Gateway Preferred`, advancing to `E3 Gateway Required` for the capabilities included in R0.1 after negative tests pass.

This Alpha slice does not claim OS-enforced prevention of direct administrator/root bypass. E4/E5 enforcement requires later OS/service-account/network/hardware controls.

## Observability
Expose, at minimum:
- service health;
- Warden decision counts;
- WEG validation failures;
- token replay detections;
- execution counts/results;
- verification failures;
- evidence write failures.

No metric should include secrets or full command payloads containing sensitive data.

## Rollout
1. contracts and fixtures;
2. Warden pure decision engine;
3. signed one-shot token;
4. WEG validator and consumed-token ledger;
5. Docker read-only adapter operations;
6. disposable-container restart;
7. verification;
8. River evidence journal;
9. negative-test suite;
10. enable R0.1 Alpha operator path.

## Acceptance Criteria
R0.1 is accepted only when:
- all contract and negative tests pass;
- an unauthorized restart cannot pass through WEG;
- an authorized restart can affect only the bound target;
- token replay is rejected;
- modified parameters are rejected;
- verification distinguishes execution from successful outcome;
- River produces a complete, hashable evidence chain;
- no secret material is committed;
- no production or physical-control capability is enabled.

## Deferred
- full GRDR/GCR database persistence;
- GDAR continuous discovery;
- GHDE health/exception engine;
- Synnergyze multi-step recovery orchestration;
- SSH/Kubernetes/credential/serial adapters;
- external agent automation;
- distributed BNR delegation;
- mobile/SIM control;
- E4/E5 enforcement;
- Control Desk UI.

These remain compatible with the R0.1 contracts and are additive future slices.