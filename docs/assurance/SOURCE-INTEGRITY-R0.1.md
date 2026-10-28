# Genesis Source Integrity and Character Encoding R0.1

Status: review-only source control proposal. No private diagram uploads, merging, hosting or release authorization.

## Contract

- HTTP Authorization is an ASCII-safe credential transport boundary. A malformed or non-ASCII credential must be rejected without execution or server 500. A Python Unicode string rejected inside httpx does not test server behavior; use transportable malformed byte-valued headers in appropriate contract tests.
- HTML, SVG, Mermaid, Markdown, multilingual labels and JSON are valid UTF-8, **not ASCII-only**. Web documents should declare UTF-8. A UTF-8 BOM is tolerated for CSV spreadsheet exports only.
- GitHub Actions generates a machine-readable manifest of tracked files with path, SHA-256, size, classification and encoding status. Binary, PDF, ZIP and SQLite files are hashed but not sent through a text decoder.
- CI only inventories Git-tracked files at the checked-out commit. An untracked archive, private source, or unmerged branch is not certified by this gate.
- The source manifest does not certify legal ownership, originality, disclosure permission, visual correctness or runtime safety. Obtain separately governed approvals before publishing any previously private diagram source.

## VSR historical inventory

VSR-DIAGRAM-REGISTRY-001 R0.1 covers 2026-09-30 to 2026-10-14 and identified 100 diagram versions; 13 had original-source bytes recovered and 87 were SOURCE_PENDING. No recovered private original is uploaded by this change. Preserve the original byte-level SHA-256 and provenance, and distinguish ORIGINAL from RECONSTRUCTED_DERIVATIVE.

## Acceptance

1. Unicode SVG and HTML are accepted; non-UTF-8 text and NUL bytes fail.
2. CI checks tracked repository contents, with an attached JSON manifest on every successful run.
3. Existing gateway authorization, no-execution and PostgreSQL assurance tests remain independently necessary.
4. No live deployment, Docker execution, Warden permission, RiverOS attestation or Silk settlement is authorized.
