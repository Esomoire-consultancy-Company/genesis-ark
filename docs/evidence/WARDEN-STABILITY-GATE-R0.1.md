# Warden Stability Gate R0.1

**Canonical object:** `WARDEN-STABILITY-GATE-001`  
**Implementation:** `control-plane/src/genesis_control_plane/stability.py`  
**Tests:** `control-plane/tests/test_stability.py`

## Purpose

This gate checks whether an already-issued Warden permit remains operationally usable under the current runtime state. It never creates, extends, or upgrades authority.

## State matrix

| State | Expected disposition | Core rule |
|---|---|---|
| Online / healthy | PROCEED | Existing permit may be used within its validity |
| Offline, local capability, evidence buffer healthy | LOCAL_ONLY | Local execution may continue without external provider dependency |
| Provider unavailable, provider not required | LOCAL_ONLY | Preserve local execution and evidence |
| Provider unavailable, provider required | DEFER | Do not silently substitute or bypass dependency |
| Reconnecting | RECONCILE | Reconcile authority/effects before normal execution |
| Credential expired | DENY | Credential expiry is a hard authority boundary |
| Clock stale | DEFER | Time-bounded authority cannot be trusted |
| Interrupted execution | DEFER | Review execution state before retry/resume |
| Uncertain external effect | RECONCILE | Never duplicate an effect whose outcome is unknown |
| Recovery mode | RECONCILE | Recovery cannot manufacture fresh authority |
| Location scope invalid | DENY | Location transition cannot widen authority |
| River remote unavailable, local buffer healthy | LOCAL_ONLY | Preserve append-only local evidence |
| No River path and no local buffer | DENY | Evidence-before-effect boundary cannot be satisfied |

## Invariants

1. The stability gate never returns execution authority of its own; `execution_authority_granted` remains false.
2. A denied Warden decision can never be upgraded.
3. An expired Warden decision can never be extended.
4. Offline mode is not unrestricted mode.
5. Reconnect and recovery require reconciliation.
6. Uncertain external effects are never automatically retried.
7. Loss of the remote River path is tolerable only when the approved local evidence buffer remains available.
8. Location scope remains an explicit authority boundary.

## Current scope

R0.1 is a pure deterministic state gate layered beside the existing Alpha Warden → one-shot token → WEG → bounded Docker adapter → verification → River evidence path.

It deliberately does **not** yet:
- issue offline authority envelopes,
- persist recovery state across reboot,
- perform provider failover,
- create local River buffering,
- mutate the existing execution service,
- or declare Genesis hardware ready.

Those require separate implementation and evidence.

## Validation

Run:

```bash
cd control-plane
python -m pytest -v -m "not docker_e2e"
```

The new matrix is additive to the existing control-plane tests and must pass on Python 3.11 and 3.12 through the existing GitHub Actions workflow.
