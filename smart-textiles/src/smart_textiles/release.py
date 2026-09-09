from typing import Any, Mapping

from .errors import ReleaseReadinessError

RELEASED_STATES = {"MODEL_RELEASED", "BATCH_RELEASED", "ITEM_ACTIVE"}
REGULATED_CLAIMS = {"medical", "ppe", "other_regulated"}


def assert_release_ready(document: Mapping[str, Any]) -> None:
    state = document.get("lifecycle_state") or document.get("passport", {}).get("status")
    if state not in RELEASED_STATES:
        return

    reasons: list[str] = []
    if not document.get("warden_decision_id") and not document.get("evidence", {}).get("warden_decision_id"):
        reasons.append("WARDEN_DECISION_REQUIRED")

    river_ids = document.get("river_receipt_ids") or document.get("evidence", {}).get("river_receipt_ids") or []
    if not river_ids:
        reasons.append("RIVER_RECEIPT_REQUIRED")

    claim = document.get("regulatory_claim_class") or document.get("application", {}).get("regulatory_claim_class", "none")
    regulatory_ids = document.get("regulatory_evidence_ids") or document.get("evidence", {}).get("conformity_record_ids") or []
    if claim in REGULATED_CLAIMS and not regulatory_ids:
        reasons.append("REGULATORY_EVIDENCE_REQUIRED")

    if reasons:
        raise ReleaseReadinessError(tuple(sorted(reasons)))
