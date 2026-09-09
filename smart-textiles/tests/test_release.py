import pytest

from smart_textiles.errors import ReleaseReadinessError
from smart_textiles.release import assert_release_ready


def test_released_model_requires_warden_and_river_references():
    model = {"lifecycle_state": "MODEL_RELEASED", "regulatory_claim_class": "none", "river_receipt_ids": []}
    with pytest.raises(ReleaseReadinessError) as exc:
        assert_release_ready(model)
    assert set(exc.value.reason_codes) == {"WARDEN_DECISION_REQUIRED", "RIVER_RECEIPT_REQUIRED"}


def test_released_model_with_authority_and_evidence_passes():
    model = {
        "lifecycle_state": "MODEL_RELEASED",
        "regulatory_claim_class": "none",
        "warden_decision_id": "WD-ST-0001",
        "river_receipt_ids": ["RVR-ST-0001"]
    }
    assert_release_ready(model)


def test_regulated_released_model_requires_regulatory_evidence():
    model = {
        "lifecycle_state": "MODEL_RELEASED",
        "regulatory_claim_class": "medical",
        "warden_decision_id": "WD-ST-0001",
        "river_receipt_ids": ["RVR-ST-0001"],
        "regulatory_evidence_ids": []
    }
    with pytest.raises(ReleaseReadinessError) as exc:
        assert_release_ready(model)
    assert exc.value.reason_codes == ("REGULATORY_EVIDENCE_REQUIRED",)
