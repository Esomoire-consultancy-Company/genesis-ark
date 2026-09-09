import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError


def validate_document(document: Mapping[str, Any], schema_name: str, schema_root: Path) -> None:
    schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.path) or "<root>"
        raise SchemaValidationError(f"{path}: {error.message}")
