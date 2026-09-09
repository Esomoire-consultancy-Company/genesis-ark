from pathlib import Path
import pytest

from genesis_control_plane.registry import AlphaRegistry, RegistryLookupError


REGISTRY = Path(__file__).parents[1] / "registry" / "alpha-registry.json"


def test_known_resource_and_capability_resolve():
    registry = AlphaRegistry.load(REGISTRY)
    resource = registry.resource("RES-RIVER-WORKER-001")
    assert resource.station_id == "GES-ALPHA-001"
    assert registry.supports(
        "RES-RIVER-WORKER-001",
        "container.instance.restart",
        "GEN-ADAPTER-DOCKER-001",
    )


def test_unknown_resource_is_rejected():
    registry = AlphaRegistry.load(REGISTRY)
    with pytest.raises(RegistryLookupError):
        registry.resource("RES-UNKNOWN")
