"""Unprivileged Warden skill discovery — explicitly NOT authorization.

Catalog metadata is untrusted until separately signed and registered by
Warden. This module does not fetch code, run tools, mint permits, or trust
a purported 'PERMIT' supplied by a caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MAX_SKILLS = 1000


class InvalidCatalog(ValueError):
    pass


@dataclass(frozen=True)
class Discovery:
    catalog_revision: str
    candidate_ids: tuple[str, ...]
    authorized: bool = False
    execution_enabled: bool = False
    reason_code: str = "WARDEN_AUTHORITY_NOT_CONNECTED"


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(_NAME.fullmatch(value))


def _scoped_list(value: Any) -> bool:
    return isinstance(value, list) and 0 < len(value) <= 100 and all(
        _identifier(item) and "*" not in item for item in value
    ) and len(set(value)) == len(value)


def discover(catalog: Mapping[str, Any], *, capability: str,
             resource_id: str, environment: str) -> Discovery:
    """Return potential skill references, never a permission decision.

    Exact matching only: no wildcards, dynamic imports, URLs, executable
    scripts, network calls, trust in catalog 'PERMIT', or fallback routes.
    An authorised executor must separately obtain a verified Warden grant.
    """
    if not all(_identifier(x) for x in (capability, resource_id, environment)):
        raise InvalidCatalog("INVALID_QUERY")
    if not isinstance(catalog, Mapping) or set(catalog) != {"revision", "skills"}:
        raise InvalidCatalog("INVALID_CATALOG_SCHEMA")
    revision, entries = catalog["revision"], catalog["skills"]
    if not _identifier(revision) or not isinstance(entries, list) or len(entries) > _MAX_SKILLS:
        raise InvalidCatalog("INVALID_CATALOG_HEADER")

    candidates: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "status", "capabilities", "resource_ids", "environments"
        }:
            raise InvalidCatalog("INVALID_DESCRIPTOR_SCHEMA")
        skill_id = entry["id"]
        if not _identifier(skill_id) or skill_id in seen:
            raise InvalidCatalog("INVALID_OR_DUPLICATE_SKILL_ID")
        seen.add(skill_id)
        if entry["status"] not in ("active", "suspended", "revoked"):
            raise InvalidCatalog("INVALID_SKILL_STATUS")
        if not all(_scoped_list(entry[key]) for key in ("capabilities", "resource_ids", "environments")):
            raise InvalidCatalog("INVALID_SKILL_SCOPE")
        if (entry["status"] == "active"
            and capability in entry["capabilities"]
            and resource_id in entry["resource_ids"]
            and environment in entry["environments"]):
            candidates.append(skill_id)

    return Discovery(catalog_revision=revision, candidate_ids=tuple(sorted(candidates)))
