from pathlib import Path
import pytest

from smart_textiles.schema_validation import SchemaValidationError, validate_document

ROOT = Path(__file__).parents[1]

VALID_MODEL = {
    "model_id": "STM-SPT-TSH-0001-R01",
    "platform_id": "STP-0001",
    "application_family": "SPT",
    "form_code": "TSH",
    "smart_architecture": {
        "integration_level": "YRN",
        "integration_method": "KNT",
        "conductive_platform": "AG"
    },
    "capability_ids": ["ST-F01", "ST-F07"],
    "power_code": "TRB",
    "revision": 1,
    "lifecycle_state": "DRAFT_CONFIG"
}


def test_valid_product_model_matches_schema():
    validate_document(VALID_MODEL, "product-model.schema.json", ROOT / "contracts")


def test_model_without_identity_is_rejected():
    invalid = dict(VALID_MODEL)
    invalid.pop("model_id")
    with pytest.raises(SchemaValidationError, match="model_id"):
        validate_document(invalid, "product-model.schema.json", ROOT / "contracts")
