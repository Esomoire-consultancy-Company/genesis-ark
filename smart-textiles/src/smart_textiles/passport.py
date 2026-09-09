from copy import deepcopy
from typing import Any, Mapping


def deep_merge(parent: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(parent))
    for key, value in child.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def assemble_passport(
    model: Mapping[str, Any],
    *,
    variant: Mapping[str, Any] | None = None,
    batch: Mapping[str, Any] | None = None,
    item: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = deepcopy(dict(model))
    for overlay in (variant, batch, item):
        if overlay is not None:
            result = deep_merge(result, overlay)
    return result
