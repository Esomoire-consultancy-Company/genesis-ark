from typing import Any, Iterable, Mapping

from .errors import SmartTextileError
from .registry import Registry


def compile_engineering_sku(model: Mapping[str, Any], registry: Registry) -> str:
    use = model["application_family"]
    registry.entry("applications", use)
    form = model["form_code"]
    registry.dictionary_entry("forms", form)

    architecture = model["smart_architecture"]
    integration = architecture["integration_level"]
    method = architecture["integration_method"]
    material = architecture["conductive_platform"]
    registry.entry("integration_levels", integration)
    registry.entry("integration_methods", method)
    registry.entry("conductive_platforms", material)

    capability_ids = sorted(model["capability_ids"])
    for capability_id in capability_ids:
        registry.entry("capabilities", capability_id)
    capability_set = "+".join(
        registry.dictionary_entry("capability_short_codes", capability_id)
        for capability_id in capability_ids
    )

    power = model["power_code"]
    registry.dictionary_entry("power", power)
    revision = int(model["revision"])
    if revision < 1:
        raise SmartTextileError("revision must be >= 1")

    return f"ST-{use}-{form}-{integration}-{method}-{capability_set}-{material}-{power}-R{revision:02d}"


def compile_catalog(models: Iterable[Mapping[str, Any]], registry: Registry) -> dict[str, Mapping[str, Any]]:
    compiled = {}
    for model in models:
        sku = compile_engineering_sku(model, registry)
        if sku in compiled:
            raise SmartTextileError(f"duplicate engineering SKU: {sku}")
        compiled[sku] = model
    return compiled
