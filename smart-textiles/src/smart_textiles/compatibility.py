from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .registry import Registry


@dataclass(frozen=True)
class CompatibilityResult:
    state: str
    reason_codes: tuple[str, ...]


def evaluate_compatibility(model: Mapping[str, Any], registry: Registry, rules_path: Path) -> CompatibilityResult:
    for capability_id in model["capability_ids"]:
        registry.entry("capabilities", capability_id)

    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    reasons: list[str] = []
    architecture = model["smart_architecture"]
    capabilities = set(model["capability_ids"])

    if capabilities.intersection(rules["body_contact_required"]) and not architecture.get("body_contact_zone"):
        reasons.append("BODY_CONTACT_ZONE_REQUIRED")

    if capabilities.intersection(rules["power_profile_required"]) and not model.get("power_profile"):
        reasons.append("POWER_PROFILE_REQUIRED")

    claim = model.get("regulatory_claim_class", "none")
    if claim in rules["regulated_claim_classes"] and not model.get("regulatory_evidence_ids"):
        reasons.append("REGULATORY_EVIDENCE_REQUIRED")

    if reasons:
        return CompatibilityResult("REJECTED_CONFIG", tuple(sorted(set(reasons))))

    prototype_reasons = {
        rules["prototype_only_capabilities"][capability]
        for capability in capabilities
        if capability in rules["prototype_only_capabilities"]
    }
    if prototype_reasons:
        return CompatibilityResult("PROTOTYPE_ONLY", tuple(sorted(prototype_reasons)))

    return CompatibilityResult("VALIDATED_CONFIG", ())
