# Genesis Engineering Station Alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Alpha-only governed execution path from a canonical command through Warden, a one-shot capability token, WEG, a bounded Docker restart, verification, and a hash-chained River evidence receipt.

**Architecture:** Implement a small Python 3.11+ package under `control-plane/` with static Alpha registry fixtures, pure Warden policy evaluation, HMAC-SHA256 capability tokens, a SQLite consumed-token ledger, a bounded Docker CLI adapter, and append-only JSONL evidence. Keep governance, enforcement, execution, verification, and evidence as separate units with typed dataclass contracts and no unrestricted shell execution.

**Tech Stack:** Python 3.11+, Python standard library (`dataclasses`, `enum`, `json`, `hashlib`, `hmac`, `base64`, `secrets`, `sqlite3`, `subprocess`, `pathlib`, `datetime`), `pytest` for tests. No Redis, Kubernetes, OPA, web framework, or new database service in R0.1.

**Spec:** `docs/superpowers/specs/2026-09-09-genesis-engineering-station-alpha-design.md`

## Global Constraints

- R0.1 is Alpha-only.
- Station ID is `GES-ALPHA-001`; node ID is `ALPHA-NODE-001`; estate ID is `GENESIS-ESTATE-001`.
- Initial adapter ID is `GEN-ADAPTER-DOCKER-001`.
- First governed mutation is exactly `container.instance.restart`.
- Deny by default for unknown capability, target, station, environment, or policy state.
- Capability tokens are HMAC-SHA256 signed, short-lived, one-shot, and bind canonical parameters by SHA-256 hash.
- Signing keys are supplied only at runtime through environment/config and are never committed.
- WEG must reject missing, invalid, expired, replayed, wrong-audience, wrong-target, wrong-adapter, or parameter-mismatched tokens.
- Docker execution is structured and bounded; no arbitrary `exec(any_string)` surface is added.
- Successful Docker process exit is not sufficient for `VERIFIED`; target state must be read back.
- River evidence is append-only and hash chained; secret/signing material is never written to evidence.
- Production, raw root/Administrator shell, destructive database operations, network/firewall mutation, secret reveal, physical/serial/BLE writes, cross-node authority, and long-lived privileged tokens are out of scope.
- R0.1 may claim at most `E2 Gateway Preferred` until all negative tests pass; only then may included capabilities advance to `E3 Gateway Required`.

---

## File Structure

```text
control-plane/
  pyproject.toml
  README.md
  registry/
    alpha-registry.json
  src/genesis_control_plane/
    __init__.py
    contracts.py
    canonical.py
    registry.py
    warden.py
    tokens.py
    weg.py
    evidence.py
    docker_adapter.py
    verifier.py
    service.py
    cli.py
  tests/
    conftest.py
    test_contracts.py
    test_registry.py
    test_warden.py
    test_tokens.py
    test_weg.py
    test_evidence.py
    test_docker_adapter.py
    test_service.py
    test_docker_e2e.py
.github/workflows/
  ges-alpha-control-plane.yml
```

Responsibilities:
- `contracts.py`: immutable command/decision/token/event/result value objects and enums.
- `canonical.py`: deterministic JSON serialization and SHA-256 helpers used by Warden/token/evidence code.
- `registry.py`: read-only Alpha registry resolver; no policy decisions.
- `warden.py`: pure deny-by-default decision engine; no execution.
- `tokens.py`: capability token issuance, signing, parsing, and signature/time validation.
- `weg.py`: enforcement checks and one-shot token consumption; no Docker-specific command construction.
- `evidence.py`: append-only JSONL writer with per-record hash chaining.
- `docker_adapter.py`: bounded Docker CLI translation for supported canonical operations only.
- `verifier.py`: Docker read-back verification distinct from execution.
- `service.py`: coordinates one command through registry → Warden → token → WEG → adapter → verifier → River evidence.
- `cli.py`: local Alpha operator entry point; no server/API surface in R0.1.

---

### Task 1: Project Scaffold, Canonical Serialization, and Contracts

**Files:**
- Create: `control-plane/pyproject.toml`
- Create: `control-plane/src/genesis_control_plane/__init__.py`
- Create: `control-plane/src/genesis_control_plane/canonical.py`
- Create: `control-plane/src/genesis_control_plane/contracts.py`
- Create: `control-plane/tests/test_contracts.py`

**Interfaces:**
- Produces: `canonical_json(value: Mapping[str, Any]) -> str`
- Produces: `sha256_hex(value: str | bytes) -> str`
- Produces: enums `DecisionResult`, `ExecutionState`, `VerificationState`
- Produces immutable dataclasses `Command`, `Decision`, `CapabilityTokenClaims`, `ExecutionResult`, `VerificationResult`, `EvidenceEvent`
- Later tasks depend on exact field names defined here.

- [ ] **Step 1: Add package metadata and test dependency**

Create `control-plane/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "genesis-control-plane-alpha"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Write failing canonicalization and contract tests**

Create `control-plane/tests/test_contracts.py`:

```python
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
```

- [ ] **Step 3: Run the tests and confirm they fail before implementation**

Run:

```bash
cd control-plane
python -m pytest tests/test_contracts.py -v
```

Expected: import failures because `canonical.py` and `contracts.py` do not yet exist.

- [ ] **Step 4: Implement deterministic serialization helpers**

Create `canonical.py`:

```python
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 5: Implement the immutable contracts**

Create `contracts.py` with frozen dataclasses using these exact signatures:

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class DecisionResult(StrEnum):
    PERMIT = "PERMIT"
    DENY = "DENY"


class ExecutionState(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationState(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class Command:
    command_id: str
    correlation_id: str
    principal_id: str
    session_id: str
    station_id: str
    adapter_id: str
    target_resource_id: str
    capability: str
    parameters: Mapping[str, Any]
    risk_class: str
    environment: str
    requested_at: str
    expires_at: str


@dataclass(frozen=True)
class Decision:
    decision_id: str
    command_id: str
    result: DecisionResult
    policy_id: str
    conditions: tuple[str, ...]
    obligations: tuple[str, ...]
    decided_at: str
    valid_until: str
    reason_code: str


@dataclass(frozen=True)
class CapabilityTokenClaims:
    token_id: str
    decision_id: str
    command_id: str
    principal_id: str
    session_id: str
    station_id: str
    adapter_id: str
    target_resource_id: str
    capability: str
    parameters_hash: str
    audience: str
    issued_at: str
    not_before: str
    expires_at: str
    max_uses: int
    nonce: str
    key_id: str


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    command_id: str
    target_resource_id: str
    state: ExecutionState
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    completed_at: str


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    execution_id: str
    target_resource_id: str
    state: VerificationState
    observed_state: str
    verified_at: str


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    event_type: str
    schema_version: str
    occurred_at: str
    station_id: str
    principal_id: str
    session_id: str
    source: str
    subject: str
    payload: Mapping[str, Any]
    correlation_id: str
    causation_id: str | None
    classification: str
```

- [ ] **Step 6: Run the contract tests**

Run:

```bash
python -m pytest tests/test_contracts.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add control-plane/pyproject.toml control-plane/src/genesis_control_plane control-plane/tests/test_contracts.py
git commit -m "feat(control-plane): add alpha contracts and canonicalization"
```

---

### Task 2: Read-Only Genesis Alpha Registry

**Files:**
- Create: `control-plane/registry/alpha-registry.json`
- Create: `control-plane/src/genesis_control_plane/registry.py`
- Create: `control-plane/tests/test_registry.py`

**Interfaces:**
- Consumes: `Command` from `contracts.py` only for tests.
- Produces: `RegistryResource`, `RegistryCapability`, `AlphaRegistry.load(path)`, `AlphaRegistry.resource(resource_id)`, `AlphaRegistry.capability(name)`, `AlphaRegistry.supports(resource_id, capability, adapter_id) -> bool`.

- [ ] **Step 1: Write failing registry tests**

```python
from pathlib import Path
import pytest

from genesis_control_plane.registry import AlphaRegistry, RegistryLookupError


REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"


def test_known_resource_and_capability_resolve():
    registry = AlphaRegistry.load(REGISTRY)
    resource = registry.resource("RES-RIVER-WORKER-001")
    assert resource.station_id == "GES-ALPHA-001"
    assert registry.supports(
        "RES-RIVER-WORKER-001",
        "container.instance.restart",
        "GEN-ADAPTER-DOCKER-001",
    )


def test_unknown_resource_is_rejected():
    registry = AlphaRegistry.load(REGISTRY)
    with pytest.raises(RegistryLookupError):
        registry.resource("RES-UNKNOWN")
```

- [ ] **Step 2: Run the tests and verify failure**

```bash
python -m pytest tests/test_registry.py -v
```

Expected: FAIL because registry module/fixture do not exist.

- [ ] **Step 3: Add the Alpha fixture**

Create `alpha-registry.json` with exact R0.1 identities:

```json
{
  "estate_id": "GENESIS-ESTATE-001",
  "station_id": "GES-ALPHA-001",
  "node_id": "ALPHA-NODE-001",
  "environment": "alpha",
  "adapters": [
    {
      "adapter_id": "GEN-ADAPTER-DOCKER-001",
      "type": "docker",
      "state": "active"
    }
  ],
  "capabilities": [
    {"name": "container.instance.list", "risk": 1, "mutation": false},
    {"name": "container.instance.inspect", "risk": 1, "mutation": false},
    {"name": "container.logs.read", "risk": 1, "mutation": false},
    {"name": "container.instance.restart", "risk": 3, "mutation": true}
  ],
  "resources": [
    {
      "resource_id": "RES-RIVER-WORKER-001",
      "canonical_name": "river-worker",
      "resource_type": "container",
      "station_id": "GES-ALPHA-001",
      "environment": "alpha",
      "adapter_id": "GEN-ADAPTER-DOCKER-001",
      "docker_name": "river-worker",
      "state": "active",
      "capabilities": [
        "container.instance.inspect",
        "container.logs.read",
        "container.instance.restart"
      ]
    }
  ]
}
```

- [ ] **Step 4: Implement the registry resolver**

Implement immutable dataclasses and strict lookup. `AlphaRegistry.supports()` must return `False` unless resource, capability, and adapter all match the fixture.

- [ ] **Step 5: Run registry tests**

```bash
python -m pytest tests/test_registry.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add control-plane/registry control-plane/src/genesis_control_plane/registry.py control-plane/tests/test_registry.py
git commit -m "feat(control-plane): add alpha resource and capability registry"
```

---

### Task 3: Deny-by-Default Warden Decision Engine

**Files:**
- Create: `control-plane/src/genesis_control_plane/warden.py`
- Create: `control-plane/tests/test_warden.py`

**Interfaces:**
- Consumes: `Command`, `Decision`, `DecisionResult`, `AlphaRegistry`.
- Produces: `WardenPolicy(policy_id="WARDEN-ENGINEERING-R0.1", max_risk=3)` and `Warden.evaluate(command, now) -> Decision`.

- [ ] **Step 1: Write failing policy tests**

Cover exactly:
- known Alpha restart -> `PERMIT`;
- unknown target -> `DENY`;
- unknown capability -> `DENY`;
- environment `production` -> `DENY`;
- station mismatch -> `DENY`;
- risk class above threshold -> `DENY`.

Use `reason_code` assertions such as `PERMITTED`, `UNKNOWN_TARGET`, `UNKNOWN_CAPABILITY`, `ENVIRONMENT_DENIED`, `STATION_DENIED`, `RISK_DENIED`.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_warden.py -v
```

- [ ] **Step 3: Implement pure evaluation**

`Warden.evaluate()` must never call Docker, write files, consume tokens, or modify registry state. Decision IDs may use `secrets.token_hex(8)` prefixed with `WD-`.

Risk mapping for R0.1:

```python
RISK_SCORE = {"low": 1, "medium": 3, "high": 6, "critical": 10}
```

Permit obligations must contain `"evidence_required"`; conditions must include `"alpha_only"` and `"one_shot_token"`.

- [ ] **Step 4: Run Warden tests**

```bash
python -m pytest tests/test_warden.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add control-plane/src/genesis_control_plane/warden.py control-plane/tests/test_warden.py
git commit -m "feat(control-plane): add deny-by-default warden policy"
```

---

### Task 4: One-Shot HMAC Capability Tokens

**Files:**
- Create: `control-plane/src/genesis_control_plane/tokens.py`
- Create: `control-plane/tests/test_tokens.py`

**Interfaces:**
- Consumes: `Command`, `Decision`, `CapabilityTokenClaims`, `canonical_json`, `sha256_hex`.
- Produces: `TokenIssuer(secret: bytes, key_id: str, audience: str)`, `issue(command, decision, now, ttl_seconds=60) -> str`, `decode_and_verify(token, now) -> CapabilityTokenClaims`.
- Token wire format: `<base64url(payload-json)>.<base64url(hmac-sha256-signature)>`.

- [ ] **Step 1: Write failing token tests**

Tests must prove:
- permit produces valid claims;
- token binds `parameters_hash == sha256_hex(canonical_json(dict(command.parameters)))`;
- modified payload fails signature validation;
- expired token fails;
- wrong audience fails;
- a DENY decision cannot issue a token.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_tokens.py -v
```

- [ ] **Step 3: Implement base64url and HMAC signing**

Use `hmac.new(secret, payload_bytes, hashlib.sha256).digest()` and `hmac.compare_digest()`; never log `secret`.

- [ ] **Step 4: Implement claim validation**

Reject when:
- `max_uses != 1`;
- audience differs;
- `not_before > now`;
- `expires_at <= now`;
- required claim missing;
- signature invalid.

Raise a dedicated `TokenValidationError` containing only a safe reason code.

- [ ] **Step 5: Run token tests**

```bash
python -m pytest tests/test_tokens.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add control-plane/src/genesis_control_plane/tokens.py control-plane/tests/test_tokens.py
git commit -m "feat(control-plane): add signed one-shot capability tokens"
```

---

### Task 5: Warden Execution Gateway and Persistent Replay Protection

**Files:**
- Create: `control-plane/src/genesis_control_plane/weg.py`
- Create: `control-plane/tests/test_weg.py`

**Interfaces:**
- Consumes: `Command`, `CapabilityTokenClaims`, `TokenIssuer.decode_and_verify`, `AlphaRegistry`, canonical parameter hashing.
- Produces: `ConsumedTokenLedger(db_path: Path)`, `is_consumed(token_id) -> bool`, `consume(token_id, command_id, consumed_at) -> None`.
- Produces: `WardenExecutionGateway.validate_and_consume(token: str, command: Command, now: datetime) -> CapabilityTokenClaims`.

- [ ] **Step 1: Write failing WEG negative tests**

Create separate tests for:
- valid token passes once;
- same token second use -> `REPLAY_DETECTED`;
- wrong target -> `TARGET_MISMATCH`;
- wrong adapter -> `ADAPTER_MISMATCH`;
- changed parameters -> `PARAMETERS_MISMATCH`;
- changed station/session/principal -> corresponding mismatch;
- registry no longer supports target/capability/adapter -> `REGISTRY_BINDING_INVALID`.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_weg.py -v
```

- [ ] **Step 3: Implement SQLite consumed-token ledger**

Create table on initialization:

```sql
CREATE TABLE IF NOT EXISTS consumed_tokens (
  token_id TEXT PRIMARY KEY,
  command_id TEXT NOT NULL,
  consumed_at TEXT NOT NULL
)
```

Use a transaction for insertion. SQLite primary-key conflict must map to `REPLAY_DETECTED`.

- [ ] **Step 4: Implement WEG binding validation**

Validation order:
1. verify token signature/time/audience;
2. compare command ID;
3. compare principal/session/station;
4. compare adapter;
5. compare target;
6. compare capability;
7. recompute parameter hash;
8. verify current registry binding;
9. atomically consume token.

Do not mark a token consumed before all binding checks pass.

- [ ] **Step 5: Run WEG tests**

```bash
python -m pytest tests/test_weg.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add control-plane/src/genesis_control_plane/weg.py control-plane/tests/test_weg.py
git commit -m "feat(control-plane): enforce token bindings and replay protection"
```

---

### Task 6: River Append-Only Hash-Chained Evidence Journal

**Files:**
- Create: `control-plane/src/genesis_control_plane/evidence.py`
- Create: `control-plane/tests/test_evidence.py`

**Interfaces:**
- Consumes: `EvidenceEvent`, `canonical_json`, `sha256_hex`.
- Produces: `EvidenceJournal(path: Path)`, `append(event) -> EvidenceReceipt`, `verify_chain() -> bool`.
- Produces: immutable `EvidenceReceipt(event_id, record_hash, previous_hash, line_number)`.

- [ ] **Step 1: Write failing evidence tests**

Prove:
- first record has `previous_hash = null`;
- second record references first hash;
- `verify_chain()` returns true for untouched file;
- changing one persisted payload causes `verify_chain()` to return false;
- event payload does not contain any signing secret because the journal API accepts only explicit `EvidenceEvent` values.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_evidence.py -v
```

- [ ] **Step 3: Implement append-only record shape**

Persist one canonical JSON object per line:

```json
{
  "event": {"...": "EvidenceEvent fields"},
  "previous_hash": null,
  "record_hash": "sha256(canonical-json-of-event-plus-previous-hash)"
}
```

Use file mode `a`, flush after each append, and reject an existing invalid chain before appending new evidence.

- [ ] **Step 4: Run evidence tests**

```bash
python -m pytest tests/test_evidence.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add control-plane/src/genesis_control_plane/evidence.py control-plane/tests/test_evidence.py
git commit -m "feat(control-plane): add hash-chained river evidence journal"
```

---

### Task 7: Bounded Docker Adapter and Independent Verification

**Files:**
- Create: `control-plane/src/genesis_control_plane/docker_adapter.py`
- Create: `control-plane/src/genesis_control_plane/verifier.py`
- Create: `control-plane/tests/test_docker_adapter.py`

**Interfaces:**
- Consumes: `RegistryResource`, `Command`, `ExecutionResult`, `VerificationResult`.
- Produces: `DockerAdapter(runner=subprocess.run)`, `restart(resource, command, now) -> ExecutionResult`, `inspect(resource) -> dict`.
- Produces: `DockerVerifier(adapter)`, `verify_restart(resource, execution, now) -> VerificationResult`.

- [ ] **Step 1: Write failing bounded-command tests with a fake runner**

Assert exact argument vectors:

```python
["docker", "restart", "--timeout", "30", "river-worker"]
```

and inspect:

```python
["docker", "inspect", "river-worker"]
```

Also assert unsupported capability raises `UnsupportedCapabilityError` and no runner call is made.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest tests/test_docker_adapter.py -v
```

- [ ] **Step 3: Implement bounded Docker calls**

Use `subprocess.run(args, capture_output=True, text=True, timeout=..., check=False)` with a list of arguments and `shell=False` implicitly. Container name comes only from the resolved registry resource; never from arbitrary user-provided shell text.

`timeout_seconds` accepted range is `1..300`; reject other values before execution.

- [ ] **Step 4: Implement verifier**

Parse `docker inspect` JSON and require:
- `.State.Running is true`;
- if `.State.Health` exists, `.State.Health.Status == "healthy"`;
- inspected name corresponds to registered resource.

Return `NOT_VERIFIED` on malformed inspect output, missing resource, non-running state, or unhealthy healthcheck.

- [ ] **Step 5: Run adapter/verifier tests**

```bash
python -m pytest tests/test_docker_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 7**

```bash
git add control-plane/src/genesis_control_plane/docker_adapter.py control-plane/src/genesis_control_plane/verifier.py control-plane/tests/test_docker_adapter.py
git commit -m "feat(control-plane): add bounded docker restart and verification"
```

---

### Task 8: End-to-End Governed Execution Service

**Files:**
- Create: `control-plane/src/genesis_control_plane/service.py`
- Create: `control-plane/tests/conftest.py`
- Create: `control-plane/tests/test_service.py`

**Interfaces:**
- Consumes: registry, Warden, token issuer, WEG, Docker adapter/verifier, evidence journal.
- Produces: `GovernedExecutionService.execute(command: Command, now: datetime) -> GovernedExecutionOutcome`.
- Produces immutable `GovernedExecutionOutcome(decision, token_id, execution, verification, evidence_receipts)`.

- [ ] **Step 1: Create reusable test fixtures**

`conftest.py` supplies:
- temporary registry copied from Alpha fixture;
- fixed HMAC secret `b"test-secret-not-production"` used only in tests;
- temporary SQLite replay ledger;
- temporary evidence JSONL;
- fake Docker runner returning deterministic restart/inspect responses.

- [ ] **Step 2: Write failing service success test**

Assert the complete chain:
1. Warden returns `PERMIT`;
2. token ID exists;
3. exactly one restart runner call occurs;
4. verification is `VERIFIED`;
5. evidence event types, in order, are:
   - `command.requested`
   - `warden.decision.created`
   - `warden.token.issued`
   - `weg.token.consumed`
   - `execution.completed`
   - `verification.completed`
   - `river.receipt.completed`
6. all events share the same correlation ID.

- [ ] **Step 3: Write failing service denial test**

For a command with environment `production` assert:
- decision is `DENY`;
- no token issued;
- Docker runner was never called;
- evidence contains request + deny decision only.

- [ ] **Step 4: Implement service orchestration**

Order must be:

```text
record command
→ Warden evaluate
→ record decision
→ if deny: return
→ issue token
→ record token metadata only
→ WEG validate+consume
→ record token consumed
→ adapter restart
→ record execution result
→ verifier read-back
→ record verification
→ record terminal receipt event
```

If adapter execution fails, still emit an execution-failed event and terminal receipt; do not claim verification success.

- [ ] **Step 5: Run service tests**

```bash
python -m pytest tests/test_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 8**

```bash
git add control-plane/src/genesis_control_plane/service.py control-plane/tests/conftest.py control-plane/tests/test_service.py
git commit -m "feat(control-plane): connect governed execution evidence loop"
```

---

### Task 9: Local Alpha CLI and Safe Configuration

**Files:**
- Create: `control-plane/src/genesis_control_plane/cli.py`
- Modify: `control-plane/pyproject.toml`
- Create: `control-plane/README.md`
- Create: `control-plane/tests/test_cli.py`

**Interfaces:**
- Produces CLI: `ges-alpha restart --resource RES-RIVER-WORKER-001 --timeout 30`.
- Reads required runtime secret from `GENESIS_WARDEN_HMAC_KEY`.
- Reads optional paths from `GENESIS_REGISTRY_PATH`, `GENESIS_REPLAY_DB`, `GENESIS_RIVER_JOURNAL` with local defaults under `.runtime/`.

- [ ] **Step 1: Write failing CLI configuration tests**

Prove:
- missing `GENESIS_WARDEN_HMAC_KEY` exits non-zero with safe message `GENESIS_WARDEN_HMAC_KEY is required`;
- resource defaults to explicit CLI argument only, never free-form Docker name;
- only `restart` subcommand exists in R0.1.

- [ ] **Step 2: Add console entry point**

Append to `pyproject.toml`:

```toml
[project.scripts]
ges-alpha = "genesis_control_plane.cli:main"
```

- [ ] **Step 3: Implement CLI command creation**

The CLI constructs a `Command` using:
- generated `CMD-...` and `CORR-...` IDs;
- principal/session from explicit CLI flags with local-alpha defaults `DM-LOCAL-OPERATOR` and `SES-LOCAL-ALPHA`;
- fixed station/adapter/environment constants;
- target resource ID from `--resource`;
- capability fixed by the `restart` subcommand;
- timeout parameter only.

Do not accept arbitrary capability names or shell strings.

- [ ] **Step 4: Document local installation and dry prerequisites**

README must show:

```bash
cd control-plane
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# bash: source .venv/bin/activate
pip install -e ".[test]"
export GENESIS_WARDEN_HMAC_KEY="replace-with-local-random-secret"
ges-alpha restart --resource RES-RIVER-WORKER-001 --timeout 30
```

Also document that `river-worker` must be the registered Alpha/test container and that direct Docker administrator access still exists outside E4 enforcement.

- [ ] **Step 5: Run CLI tests**

```bash
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 9**

```bash
git add control-plane/pyproject.toml control-plane/src/genesis_control_plane/cli.py control-plane/tests/test_cli.py control-plane/README.md
git commit -m "feat(control-plane): add safe alpha operator cli"
```

---

### Task 10: Disposable Docker End-to-End Acceptance and Negative Tests

**Files:**
- Create: `control-plane/tests/test_docker_e2e.py`
- Modify: `control-plane/registry/alpha-registry.json` only if a dedicated fixture resource is safer than reusing `RES-RIVER-WORKER-001`; if modified, use `RES-GES-TEST-CONTAINER-001` and `docker_name: ges-alpha-test`.

**Interfaces:**
- Consumes full service from Task 8.
- Produces proof that a real Docker engine enforces the bound target and one-shot token semantics.

- [ ] **Step 1: Add Docker availability guard**

Use `shutil.which("docker")` and `docker info` to skip, not fail, when Docker is unavailable in generic CI.

- [ ] **Step 2: Create disposable test container in fixture setup**

Use a harmless image such as `alpine:3.20` with a long-running command:

```bash
docker run -d --name ges-alpha-test alpine:3.20 sh -c "while true; do sleep 60; done"
```

Teardown must remove it:

```bash
docker rm -f ges-alpha-test
```

- [ ] **Step 3: Write real authorized restart test**

Capture container start/restart metadata before and after and assert:
- Warden permits;
- WEG consumes token;
- container restart occurred;
- verifier returns `VERIFIED`;
- evidence chain verifies.

- [ ] **Step 4: Write replay negative test against the same token**

Call WEG a second time with the same token and assert `REPLAY_DETECTED`; ensure no second Docker restart call is executed.

- [ ] **Step 5: Write parameter-tampering negative test**

Issue token for timeout `30`, change command timeout to `31`, and assert `PARAMETERS_MISMATCH` before Docker is invoked.

- [ ] **Step 6: Run unit suite and Docker e2e suite**

```bash
python -m pytest -v
```

Expected: all unit tests PASS; Docker e2e PASS where Docker exists, otherwise explicit SKIP.

- [ ] **Step 7: Commit Task 10**

```bash
git add control-plane/tests/test_docker_e2e.py control-plane/registry/alpha-registry.json
git commit -m "test(control-plane): prove governed docker restart end to end"
```

---

### Task 11: CI Gate and R0.1 Verification Record

**Files:**
- Create: `.github/workflows/ges-alpha-control-plane.yml`
- Create: `docs/evidence/GES-ALPHA-CONTROL-PLANE-R0.1.md`
- Modify: `README.md`

**Interfaces:**
- Produces CI gate for all non-Docker unit tests on Python 3.11 and 3.12.
- Produces repository evidence summary that distinguishes verified source/CI state from local Docker-runtime validation.

- [ ] **Step 1: Add GitHub Actions unit-test workflow**

Workflow:

```yaml
name: GES Alpha Control Plane

on:
  pull_request:
    paths:
      - "control-plane/**"
      - ".github/workflows/ges-alpha-control-plane.yml"
  push:
    branches: [main]
    paths:
      - "control-plane/**"

jobs:
  unit:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e "control-plane[test]"
      - run: python -m pytest control-plane/tests -v -m "not docker_e2e"
```

Mark Docker e2e using `pytest.mark.docker_e2e` and register the marker in `pyproject.toml`.

- [ ] **Step 2: Run the complete local unit suite before committing**

```bash
cd control-plane
python -m pytest -v -m "not docker_e2e"
```

Expected: PASS with zero failures.

- [ ] **Step 3: Create R0.1 verification record**

Document:
- design/spec commit;
- implementation branch;
- unit test command/results;
- negative tests covered;
- whether Docker e2e was actually executed;
- remaining limitation: direct administrator/root Docker access is outside the gateway until E4 controls exist;
- maturity remains E2 unless real Docker e2e + negative tests have passed.

Do not claim E3 if Docker e2e has not actually run successfully.

- [ ] **Step 4: Link the control plane from root README**

Add a short `Genesis Engineering Station Alpha Control Plane` section linking to:
- design spec;
- implementation plan;
- `control-plane/README.md`;
- verification record.

- [ ] **Step 5: Commit Task 11**

```bash
git add .github/workflows/ges-alpha-control-plane.yml docs/evidence/GES-ALPHA-CONTROL-PLANE-R0.1.md README.md control-plane/pyproject.toml
git commit -m "ci(control-plane): gate ges alpha governance path"
```

---

## Final Verification Checklist

Run from `control-plane/`:

```bash
python -m pytest -v -m "not docker_e2e"
```

Required: zero failures.

When a Docker engine is available:

```bash
python -m pytest tests/test_docker_e2e.py -v
```

Required before E3 promotion:
- authorized restart passes;
- replay rejected;
- parameter tampering rejected;
- wrong target rejected;
- wrong adapter rejected;
- wrong audience rejected;
- expired token rejected;
- invalid signature rejected;
- River evidence chain verifies;
- no secret material appears in source or evidence.

Repository checks:

```bash
git diff --check
git status --short
```

Required: no whitespace errors and only intentional changes.

## Spec Coverage Self-Review

- Canonical Alpha registry: Tasks 2 and 10.
- Deny-by-default Warden: Task 3.
- One-shot signed capability token: Task 4.
- WEG binding checks/replay protection: Task 5.
- Bounded Docker operation: Task 7.
- Independent verification: Task 7.
- River append-only evidence: Task 6.
- Complete command → decision → token → WEG → Docker → verification → evidence loop: Task 8.
- Safe local operator path: Task 9.
- Negative and end-to-end tests: Task 10.
- CI/readiness evidence: Task 11.
- Explicit E2/E3 boundary and no E4 claim: Global Constraints + Task 11.

No R0.1 requirement is intentionally left without an implementation or verification task.