"""VSR-FOR-001 R0.3 public reference discovery. NOT a Warden/engine/evidence authority."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class NavigationDecision:
    disposition: str
    reason: str
    real_authority: bool = False
    execution_allowed: bool = False
    river_receipt_emitted: bool = False

def public_catalogue(catalogue: Mapping[str, Any], query: str = "") -> dict:
    """Allowlist only safe metadata of public, proposed framework objects."""
    query = query.strip().casefold()
    safe = []
    for item in catalogue.get("frameworks", []):
        if item.get("visibility") != "public" or item.get("registered") is not False:
            continue
        if not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str):
            continue
        roles = item.get("roles", [])
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            continue
        if query and query not in (item["id"] + " " + item["name"] + " " + " ".join(roles)).casefold():
            continue
        safe.append({"id": item["id"], "name": item["name"], "roles": list(roles),
                     "status": "PROPOSED_UNREGISTERED", "execution_allowed": False})
    return {"status": "PUBLIC_REFERENCE_PREVIEW", "count": len(safe),
            "frameworks": safe, "private_data_included": False}

def assess_navigation(request: Mapping[str, Any]) -> NavigationDecision:
    """Fail closed for protected navigation; never trust client-side permit claims."""
    action = request.get("action")
    if action == "browse.public":
        if request.get("route_request") or request.get("execute") or request.get("resource_id"):
            return NavigationDecision("DENY", "PUBLIC_PREVIEW_SCOPE_EXCEEDED")
        return NavigationDecision("PUBLIC_PREVIEW", "PUBLIC_METADATA_ONLY")
    if action == "navigate.readonly":
        if request.get("execute") or request.get("mutation"):
            return NavigationDecision("DENY", "MUTATION_DISALLOWED")
        return NavigationDecision("HOLD", "LIVE_REGISTRY_AND_WARDEN_BINDING_REQUIRED")
    return NavigationDecision("DENY", "ACTION_NOT_SUPPORTED")
