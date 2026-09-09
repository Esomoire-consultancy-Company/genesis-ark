from pathlib import Path
import pytest

from smart_textiles.errors import UnknownRegistryCode
from smart_textiles.registry import Registry

ROOT = Path(__file__).parents[1]


def test_registry_loads_canonical_r01_counts_and_labels():
    registry = Registry.load(ROOT / "registry")
    assert registry.codes("integration_levels") == ("FAB", "FBR", "YRN")
    assert registry.codes("integration_methods") == ("EMB", "KNT", "WVN")
    assert registry.codes("conductive_platforms") == ("AG", "CNT", "CPY", "CU", "STL")
    assert len(registry.codes("capabilities")) == 17
    assert registry.entry("capabilities", "ST-F01")["name"] == "ECG / biopotential sensing"
    assert registry.entry("applications", "SPT")["name"] == "Sport / performance"


def test_registry_rejects_unknown_code():
    registry = Registry.load(ROOT / "registry")
    with pytest.raises(UnknownRegistryCode, match="NOPE"):
        registry.entry("capabilities", "NOPE")
