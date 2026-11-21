# VSR-FOR-001 — Phase 10 Attribution, Applicability & Qualification (R1.0)

**Status: DRAFT — source identification and semantic-review packet. Nothing has been registered, approved, executed or deployed.**

## Why this phase exists

Framework references are historical, mathematical, scientific or internally proposed concepts. The metaphorical labels `road`, `navigation`, `checkpoint`, `bridge` and `engine candidate` are **VSR transport-role metadata**, independent of intellectual authorship, implementation capabilities and governance. A paper's presence as a node does not establish that two connected papers are logically derived from one another, or that a physics theory provides a transportation capability.

## Attribution rules

1. Preserve official original names, credited authors and publication dates for identifiable works. EPR (1935), HRT (2007), GJW (2016 preprint) and the Byzantine Generals Problem (1982) are distinct publications with identifiable authors.
2. Historical precursor != exact creator. Francis J. Aguilar's *Scanning the Business Environment* (1967) is an important environmental-scanning precursor; the later PESTLE/PESTEL acronym cannot be assigned exclusively to him from this material.
3. General fields and techniques (`differential equations`, `feedback control`, `mass balance`, `historical precedent comparison`, `NPV`) must not have invented sole inventors. A relevant cited paper is not proof of sole invention of the field.
4. VSR workflow patterns (`Planner–Checker–Approver`, `Sensing → Relevance → Matching`) require a separate internal originator/provenance record. Do not invent a person, or claim external invention, before signed internal evidence is gathered.
5. URLs in `phase10_qualification_dossiers.json` identify **candidate sources**, not completed bibliographic, copyright, legal, empirical or technical reviews. Source material must be checked by reviewers before use as authoritative citations.
6. `road` relationships include **pedagogical, procedural, analogy, engineering and governance** links. The EPR → HRT → GJW route is a pedagogical sequence, *not* a theorem that each paper derives from the preceding one; none of them provides deployable physical transit.

## Current review packet counts

| Field | Quantity | Meaning |
|---|---:|---|
| Proposed framework records | 14 | Provisional reference objects, zero live IDs |
| Citation identified / unaudited | 9 | At least one candidate reference link |
| Source identification or internal provenance pending | 5 | No direct candidate URL in dossier |
| Proposed directed edges | 13 | Conceptual links, not validated scientific relationships |
| Explicit cross-station bridges | 6 | Not approved |
| Qualified edge / framework implementations | 0 | No reviewer has signed off |
| Genesis registrations / Warden permits / River receipts | 0 | No live services connected |

## Executable checks

`phase10_review_gate.py` checks dossier lineage against the original two manifests, one-to-one IDs, attribution classes and sources, HTTPS source fields, applicability/limitations, semantic classifications, and denial of invented credentials, human approval, rights clearance, scientific derivation, engine qualification or Warden authority. The successful outcome is **`REVIEW_PACKET_READY_WITH_BLOCKERS`** and all authority flags false. It never opens URLs, contacts a provider or issues approvals.

Run from this directory:

```bash
python3 -m unittest discover -s knowledge-roads -p 'test_phase10_review_gate.py' -v
python3 knowledge-roads/phase10_report.py
```

The first command runs Phase 10 local contract tests; the second prints a deterministic summary and reviewer checklist. Full-repository tests should be run separately in GitHub Actions. The local test results are not proof of live-source review, operational permission or compliance.

## Human-review and evidence handoff

Before registration, qualified reviewers must compare citation metadata to original material, confirm applicability and limitations for the intended knowledge station, check publishing/usage rights, independently review each proposed edge/bridge (especially the scientific research sequence), and document review decisions and rejection rationale. A signed approved registry object, Warden navigation policy and RiverOS receipt each require independent systems and a separate authorized change process. The current public repository is not that registrar or authorization service.

## Sources for independent follow-up (examples)

- Einstein–Podolsky–Rosen, *Physical Review* **47**, 777 (1935): https://doi.org/10.1103/PhysRev.47.777
- Hubeny–Rangamani–Takayanagi, *JHEP* 07 (2007) 062: https://doi.org/10.1088/1126-6708/2007/07/062
- Gao–Jafferis–Wall, theoretical paper preprint: https://arxiv.org/abs/1608.05687
- Lamport–Shostak–Pease, 1982: https://www.microsoft.com/en-us/research/publication/byzantine-generals-problem/
- Bayes (communicated by Richard Price in 1763): https://www.jstor.org/stable/105741
- Kalman, 1960 (filtering; not sole origin of state observers): https://doi.org/10.1115/1.3662552
- Aguilar, 1967, publisher/library catalog: https://books.google.com/books/about/Scanning_the_Business_Environment_Franci.html?id=0KkuwAEACAAJ
- Recent origin scholarship on PEST: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5644046
- MIT OpenCourseWare, feedback control: https://ocw.mit.edu/courses/2-14-analysis-and-design-of-feedback-control-systems-spring-2014/pages/syllabus/

**Nothing in this reference packet constitutes legal advice, scientific certification, IP ownership or engineering assurance.**