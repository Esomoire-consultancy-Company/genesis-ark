from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from .errors import UnknownRegistryCode

FILES = {
    "integration_levels": "integration-levels.yaml",
    "integration_methods": "integration-methods.yaml",
    "conductive_platforms": "conductive-platforms.yaml",
    "capabilities": "capabilities.yaml",
    "applications": "applications.yaml",
}


@dataclass(frozen=True)
class Registry:
    data: Mapping[str, Mapping[str, Mapping[str, Any]]]
    dictionary: Mapping[str, Any]

    @classmethod
    def load(cls, root: Path) -> "Registry":
        loaded = {}
        for kind, filename in FILES.items():
            records = yaml.safe_load((root / filename).read_text(encoding="utf-8"))
            by_code = {record["code"]: MappingProxyType(dict(record)) for record in records}
            if len(by_code) != len(records):
                raise ValueError(f"duplicate registry code in {filename}")
            loaded[kind] = MappingProxyType(by_code)
        dictionary = yaml.safe_load((root / "code-dictionary.yaml").read_text(encoding="utf-8"))
        return cls(MappingProxyType(loaded), MappingProxyType(dictionary))

    def codes(self, kind: str) -> tuple[str, ...]:
        return tuple(sorted(self.data[kind]))

    def entry(self, kind: str, code: str) -> Mapping[str, Any]:
        try:
            return self.data[kind][code]
        except KeyError as exc:
            raise UnknownRegistryCode(f"unknown {kind} code: {code}") from exc

    def dictionary_entry(self, group: str, code: str) -> str:
        try:
            return self.dictionary[group][code]
        except KeyError as exc:
            raise UnknownRegistryCode(f"unknown {group} code: {code}") from exc
