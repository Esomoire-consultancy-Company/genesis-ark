# VSR-FOR-001 R0.9 — Reference Routes and Admission Readiness

**STATUS: DRAFT ONLY — public knowledge preview. Not an authoritative Genesis registry, DigitalMe identity verification, Warden permit, RiverOS receipt or engine runtime.**

## What is new

Phase 9 converts the 14 provisional framework references into a **directed, version-sensitive graph of 13 explicit conceptual transitions**. Every edge is an independently reviewable candidate. The graph does not infer travel merely because two frameworks share a Knowledge Station, nor infer a reverse route from a forward edge.

A framework can serve as a *road*, *navigation reference*, *checkpoint* or *engine candidate*. These roles never turn a theorem into a physical transport system, qualified engine, or automatically authorized agent action. Every cross-Knowledge-Station transfer is an explicit `bridge` object, initially unqualified. Source attribution and technical qualification still require independent review.

The two preview modes have precisely bounded meaning:

- `fewest-hops` counts explicit directed conceptual transitions. It is not the shortest physical route or the fastest operational answer.
- `fewer-bridges` adds a **hypothetical review-complexity penalty** for cross-station bridges. It is not a measured budget, tariff, energy amount, legal exposure or safety score.

Each displayed route includes a SHA-256 *public fingerprint* bound to the ordered framework versions, explicit edge IDs, their station scopes, qualification states and routing mode. That hash is **not a cryptographic signature** and cannot be used as an authorization token.

## The four initial routes

| Intent | Source | Destination | Intended conceptual references |
| --- | --- | --- | --- |
| Village development | `FOR-0001` PESTEL | `FOR-0006` Sensing–Relevance–Matching | Planning, precedent, finance, governance, observability |
| Buffet sensing / replenishment | `FOR-0008` state observer | `FOR-0006` Sensing–Relevance–Matching | State estimation, mass balance, feedback and governance |
| Quantum research | `FOR-0010` EPR | `FOR-0012` GJW | EPR, HRT, GJW — research navigation only |
| Distributed-system reliability | `FOR-0013` Byzantine Generals Problem | `FOR-0006` Sensing–Relevance–Matching | Distributed systems, feedback and governance |

The preview output does not grant authority. For **every route**, an actual `navigate.readonly` request returns **HOLD** pending separately trusted, real-world admission. `engine.execute` is denied.

## Registration and policy blockers

- All 14 objects remain `PROPOSED_LOCAL_ONLY` with no authoritative Genesis IDs or signed attestations.
- Every edge remains `PROPOSED_ONLY` (13 unqualified edges); 6 of the 13 are explicit cross-station bridge proposals.
- Original source attribution, conditions of applicability, edge qualifications, version control and revocation checks must be independently established.
- Independently verified DigitalMe principal, consent, purpose and mandate are not connected.
- A separate scoped Warden `navigate.readonly` policy is not connected; Engineering Station Alpha's Docker restart capability cannot be repurposed.
- RiverOS must issue authentic, reconcilable evidence of authorized route transitions; a demo result is never a River receipt.
- Protected execution requires **separate** engine qualification, action-scoped Warden admission, human review, rollback and transaction governance.

## Usage / verification

From the project root:

```shell
python3 knowledge-roads/phase9_demo.py
python3 -m unittest discover -s knowledge-roads -p 'test_*.py' -v
```

The demo reads *only* `registration_proposals.json` (present in the earlier draft PR) and `phase9_proposed_edges.json`. It has no external dependencies or network path. The new `test_phase9_route_compiler.py` suite covers graph consistency, directed paths, version binding, unqualified bridges, station scope, fake registration/authority claims and blocked protected actions.

**Admission readiness is not an authorization decision.** Even if metadata is later marked qualified, only a separate independently trusted Warden decision verifier and real Genesis/ DigitalMe source can authorize protected navigation. No code here may upgrade preview status to production PERMIT.