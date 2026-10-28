#!/usr/bin/env bash
# Safe non-mutating preflight: only stages files with an explicit --stage flag.
set -euo pipefail
EXPECTED_BRANCH='test/genesis-synthetic-baseline-r01'
if [[ "$(git rev-parse --is-inside-work-tree 2>/dev/null || true)" != true ]]; then
  echo 'ERROR: run inside an existing genesis-ark checkout, after extracting the package.' >&2; exit 2
fi
current=$(git branch --show-current)
if [[ "$current" != "$EXPECTED_BRANCH" ]]; then
  echo "ERROR: current branch '$current', expected '$EXPECTED_BRANCH'. No changes staged." >&2; exit 2
fi
if [[ ! -f synthetic-baseline/verify.py || ! -f synthetic-baseline/fixtures.json ]]; then
  echo 'ERROR: extract package into this repository checkout first.' >&2; exit 2
fi
python3 synthetic-baseline/verify.py >/dev/null
python3 -m unittest discover -s synthetic-baseline -p 'test_*.py' -q
if command -v node >/dev/null 2>&1; then node --check synthetic-baseline/workbench/workbench.js; fi
if [[ "${1:-}" == '--stage' ]]; then
  git add synthetic-baseline/ docs/BASELINE_EVIDENCE_R02.md docs/SYNTHETIC_CONSUMER_MAPPING_R02.md docs/CI_FAILURE_TRIAGE_R01.md docs/SYNTHETIC_BASELINE_R02_PACKAGE_NOTES.md .github/workflows/genesis-synthetic-baseline.yml tools/prepare_browser_retry.py tools/browser_workbench_qa.py tools/verify_package.py tools/prepare_review_branch.sh
  echo 'Files staged on the expected branch. Review with: git diff --cached'
  echo 'No commit, push, PR, merge or deployment was performed.'
else
  echo 'PASS: local checks. No files staged, committed, pushed or deployed.'
  echo "For staging on ${EXPECTED_BRANCH}, rerun with --stage after reviewing the package."
fi
