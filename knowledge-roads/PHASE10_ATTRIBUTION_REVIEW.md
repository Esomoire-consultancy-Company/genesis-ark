# VSR-FOR-001 R0.10 — Original Attribution and Relationship Qualification

**Status: DRAFT / source-review preparation only. All 14 framework objects remain unregistered; all 13 directed transitions remain unqualified.**

This phase maintains two distinct records:

1. **Original scholarship/methodology** — established names, original author credit where reliably identified, publication/source leads, applicability assumptions and non-applicability. This is a scholarly provenance record; it is not a claim of IP ownership.
2. **VSR Knowledge Roads relationships** — explicitly curated, directional links between references. A pedagogical sequence, workflow handoff or cross-disciplinary analogy is not automatically a scientific implication or a qualified infrastructure connection.

## Materials

- \`phase10_qualification_dossiers.json\`: 14 individual framework attribution dossiers and 13 edge review records, linked to the R0.4 registration proposals and R0.9 proposed graph.
- \`phase10_qualification.py\`: purely local verifier for complete coverage, anti-escalation fields, source URL syntax, basic attribution/applicability metadata and explicit non-derivation of quantum research links.
- \`test_phase10_qualification.py\`: adversarial tests covering false attribution certification, grants, missing files, unauthorized engines, invalid source URLs, fake bridge approval and deterministic review fingerprint changes.

## Attribution examples

| Reference | Grounded source lead | Qualification note |
| --- | --- | --- |
| FOR-0002 — Bayes' theorem | Bayes (1763), Philosophical Transactions, doi:10.1098/rstl.1763.0053 | Richard Price communicated the work; subsequent formulations extended the theorem |
| FOR-0008 — state observer | Kalman (1960), doi:10.1115/1.3662552 | Kalman filtering is related to state estimation; do not treat it as invention of all observers |
| FOR-0010 — EPR | Einstein, Podolsky and Rosen (1935), doi:10.1103/PhysRev.47.777 | Scholarship only; no physical transit |
| FOR-0011 — HRT | Hubeny, Rangamani and Takayanagi (2007), arXiv:0705.0016 / doi:10.1088/1126-6708/2007/07/062 | A covariant holographic entanglement proposal, not derived directly from the EPR paper |
| FOR-0012 — GJW | Gao, Jafferis and Wall, arXiv:1608.05687 | Specific theoretical traversability model, not real-world transport |
| FOR-0013 — Byzantine Generals Problem | Lamport, Shostak and Pease (1982), Microsoft Research publisher record | Requires a defined fault model and protocol |
| FOR-0001 — PESTEL | Environmental-scanning antecedents | No proven sole original author of the modern acronym; attribution review pending |

For broad methods such as differential equations, mass balance, feedback control, NPV and historical comparison, do not invent a singular inventor. VSR's Planner–Checker–Approver and Sensing–Relevance–Matching are internal pattern names whose original ideation evidence and originating human controller still require attestation.

The cited URLs are **review leads**, not confirmation that the cited text has been fully examined or that the source is relevant to every use case. Copyright, licensing, scientific review, version and jurisdiction checks remain separate.

## Relationship review

- There are 13 proposed edges, including 6 cross-Knowledge-Station bridges.
- \`QNT-01\` EPR → HRT and \`QNT-02\` HRT → GJW are classified as **pedagogical reading sequences, not derivations**.
- Planning, engineering and governance links are user-experience or workflow proposals, not proven scientific causal paths.
- A framework's status as \`engine\` means **candidate application only**; no execution policy, production implementation or device permissions are inferred.

## Validation and release gates

\`\`\`shell
python3 -m unittest discover -s knowledge-roads -p 'test_*.py' -v
\`\`\`

The R0.10 audit accepts only the original proposal-only manifest, matching 14 dossier IDs and 13 edge IDs, recorded limits, and entirely unapproved review fields. The strongest output is:

\`\`\`
disposition = "HOLD"
reason = "UNATTESTED_SOURCES_AND_UNQUALIFIED_TRANSITIONS"
genesis_registration_allowed = false
warden_navigation_allowed = false
engine_execution_allowed = false
river_receipt_emitted = false
publish_approved = false
\`\`\`

\`fingerprint\` is an unsigned SHA-256 review checksum, not a registered identity or signed authorization.

**To qualify an actual relationship later:** independent scholarly or domain reviewer, reviewed source/rights citation, applicability scope and tests, designated human originator/controller, Warden verification and a separate Genesis registrar. Do not simply change a review field to "approved"; use a new authenticated admission workflow. Existing Engineering Station Alpha permissions remain unchanged.
