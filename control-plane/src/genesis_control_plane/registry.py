from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class RegistryLookupError(KeyError):
    pass


@dataclass(frozen=True)
class RegistryCapability:
    name: str
    risk: int
    mutation: bool


@dataclass(frozen=True)
class RegistryResource:
    resource_id: str
    canonical_name: str
    resource_type: str
    station_id: str
    environment: str
    adapter_id: str
    docker_name: str
    state: str
    capabilities: tuple[str, ...]


class AlphaRegistry:
    def __init__(self, data: dict):
        self.estate_id = data["estate_id"]
        self.station_id = data["station_id"]
        self.node_id = data["node_id"]
        self.environment = data["environment"]
        self._capabilities = {
            item["name"]: RegistryCapability(
                name=item["name"], risk=int(item["risk"]), mutation=bool(item["mutation"])
            )
            for item in data["capabilities"]
        }
        self._resources = {
            item["resource_id"]: RegistryResource(
                resource_id=item["resource_id"],
                canonical_name=item["canonical_name"],
                resource_type=item["resource_type"],
                station_id=item["station_id"],
                environment=item["environment"],
                adapter_id=item["adapter_id"],
                docker_name=item["docker_name"],
                state=item["state"],
                capabilities=tuple(item["capabilities"]),
            )
            for item in data["resources"]
        }

    @classmethod
    def load(cls, path: Path) -> "AlphaRegistry":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def resource(self, resource_id: str) -> RegistryResource:
        try:
            return self._resources[resource_id]
        except KeyError as exc:
            raise RegistryLookupError(resource_id) from exc

    def capability(self, name: str) -> RegistryCapability:
        try:
            return self._capabilities[name]
        except KeyError as exc:
            raise RegistryLookupError(name) from exc

    def supports(self, resource_id: str, capability: str, adapter_id: str) -> bool:
        try:
            resource = self.resource(resource_id)
            self.capability(capability)
        except RegistryLookupError:
            return False
        return (
            resource.state == "active"
            and resource.adapter_id == adapter_id
            and capability in resource.capabilities
        )
