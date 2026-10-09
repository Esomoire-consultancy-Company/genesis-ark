#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-Esomoire-consultancy-Company/genesis-ark}"
command -v gh >/dev/null || { echo "GitHub CLI (gh) is required" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Authenticate with gh auth login first" >&2; exit 1; }
EXISTING="$(gh label list --repo "$REPO" --limit 400 --json name --jq '.[].name')"
while IFS='|' read -r name color desc; do
  [[ -z "$name" ]] && continue
  if grep -Fxq "$name" <<<"$EXISTING"; then echo "EXISTS: $name"; continue; fi
  gh label create "$name" --repo "$REPO" --color "$color" --description "$desc"
  echo "CREATED: $name"
done <<'LABELS'
module:bmp-market|2B7A78|BMP frontend market, listings, leads
module:synnergyze-support|3D6E9C|Provider field-ops and implementation
module:quantum-room|684CB3|Live spatial scheduling and runtime
module:digitalme|7E9A2A|Identity, contribution and granted rights
module:bnr-evidence|965547|Review, governance and River provenance
module:scotts-amd|D8A041|A-1204 pilot
type:pilot|428D6A|Demonstration pilot
priority:p0|CB4B39|Immediate high priority
status:intake|6D7872|Awaiting spec readiness
LABELS
