from copy import deepcopy
from pathlib import Path

from smart_textiles.passport import assemble_passport
from smart_textiles.schema_validation import validate_document

ROOT = Path(__file__).parents[1]

MODEL = {
    "passport": {"passport_id": "DPP-MODEL-001", "passport_level": "model", "schema_version": "0.1", "status": "ENGINEERING_VALIDATED"},
    "identity": {"platform_id": "STP-0001", "model_id": "STM-0001-R01", "human_readable_sku": "ST-SPT-TSH-YRN-KNT-ECG+TMP-AG-TRB-R01"},
    "application": {"application_family": "SPT", "intended_use": "athletic monitoring"},
    "textile": {"fibre_composition": "polyamide/elastane"},
    "smart_architecture": {"integration_level": "YRN", "integration_method": "KNT", "conductive_platform": "AG"},
    "capabilities": {"capability_ids": ["ST-F01", "ST-F07"]},
    "power": {"source_types": ["TRB"]},
    "electronics": {"firmware_version": "1.0.0"},
    "performance": {},
    "safety": {},
    "manufacturing": {},
    "traceability": {},
    "circularity": {},
    "evidence": {"river_receipt_ids": []}
}


def test_variant_and_item_inherit_without_mutating_model():
    original = deepcopy(MODEL)
    variant = {"identity": {"commercial_variant_id": "VAR-BLK-M"}, "commercial": {"colour": "black", "size": "M"}}
    item = {"passport": {"passport_id": "DPP-ITEM-001", "passport_level": "item"}, "identity": {"item_id": "ITEM-0001"}, "electronics": {"firmware_version": "1.0.1"}}
    result = assemble_passport(MODEL, variant=variant, item=item)
    assert result["identity"]["model_id"] == "STM-0001-R01"
    assert result["identity"]["commercial_variant_id"] == "VAR-BLK-M"
    assert result["identity"]["item_id"] == "ITEM-0001"
    assert result["electronics"]["firmware_version"] == "1.0.1"
    assert MODEL == original


def test_batch_overlay_preserves_model_identity():
    batch = {"identity": {"batch_id": "BATCH-0001"}, "manufacturing": {"production_line": "LINE-07"}}
    result = assemble_passport(MODEL, batch=batch)
    assert result["identity"]["model_id"] == "STM-0001-R01"
    assert result["identity"]["batch_id"] == "BATCH-0001"
    assert result["manufacturing"]["production_line"] == "LINE-07"


def test_assembled_item_remains_passport_schema_valid():
    item = {"passport": {"passport_id": "DPP-ITEM-001", "passport_level": "item"}, "identity": {"item_id": "ITEM-0001"}}
    result = assemble_passport(MODEL, item=item)
    validate_document(result, "product-passport.schema.json", ROOT / "contracts")
