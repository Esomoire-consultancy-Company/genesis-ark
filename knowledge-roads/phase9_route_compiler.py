"""VSR-FOR-001 R0.9: public intellectual-route compilation and admission blockers.

This module deliberately performs NO network I/O, service authority verification,
role assignment, execution or RiverOS evidence writing. Preview topology and
catalogue labels never constitute authoritative Genesis registrations.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import heapq
import json
from typing import Any, Mapping


ALLOWED_ACTIONS = frozenset(("browse.public", "navigate.readonly"))
MODES = frozenset(("fewest-hops", "fewer-bridges"))
STATES = frozenset(("PROPOSED_ONLY", "CANDIDATE_FOR_REVIEW"))
ROLES = frozenset(("road", "navigation", "engine", "checkpoint", "bridge"))


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= 256


@dataclass(frozen=True)
class RoutePreview:
    disposition: str
    reason: str
    references: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    station_hops: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()
    public_route_digest: str | None = None
    # Explicitly FALSE for all locally computed previews, including "success".
    authority_granted: bool = False
    engine_execution_allowed: bool = False
    river_receipt_emitted: bool = False
    registered_in_genesis: bool = False
    deploy_allowed: bool = False


class InvalidTopology(ValueError):
    pass


class PreviewGraph:
    """Directed graph of *proposed* public framework relationships.

    Only explicit directed edges can be traversed. Shared Knowledge Stations
    never imply a road, and a cross-station edge needs a distinct bridge record.
    All weights are illustrative and make NO real time/cost/risk claim.
    """

    def __init__(self, proposal_manifest: Mapping[str, Any], edge_manifest: Mapping[str, Any]):
        if (proposal_manifest.get("status") != "PROPOSAL_ONLY_NOT_REGISTERED"
                or proposal_manifest.get("registration_count") != 0
                or proposal_manifest.get("registration_action_requested") is not False):
            raise InvalidTopology("Expected a non-authorizing proposal-only catalog")
        source_objects = proposal_manifest.get("objects")
        if not isinstance(source_objects, list) or not 0 < len(source_objects) <= 250:
            raise InvalidTopology("Invalid framework catalogue")
        self.nodes: dict[str, dict] = {}
        for item in source_objects:
            if not isinstance(item, dict):
                raise InvalidTopology("Invalid framework record")
            sid = item.get("source_framework_id")
            if not _text(sid) or sid in self.nodes:
                raise InvalidTopology("Invalid or duplicate framework ID")
            if (item.get("registration_state") != "PROPOSED_LOCAL_ONLY"
                    or item.get("external_registry_id") is not None
                    or item.get("authority_grant") is not False
                    or item.get("engine_execution_authorized") is not False):
                raise InvalidTopology("Public preview must not claim registration or authority")
            stations = item.get("knowledge_station_ids")
            roles = item.get("transport_roles")
            if (not _text(item.get("canonical_name"))
                    or not _text(item.get("framework_version"))
                    or not isinstance(stations, list) or not stations
                    or any(not _text(s) for s in stations)
                    or len(stations) != len(set(stations))
                    or not isinstance(roles, list) or not roles
                    or not all(isinstance(r, str) and r in ROLES for r in roles)):
                raise InvalidTopology("Incomplete framework preview metadata")
            self.nodes[sid] = item

        if edge_manifest.get("status") != "PROPOSED_ONLY_NO_AUTHORITY":
            raise InvalidTopology("Topology must be a proposal only")
        if edge_manifest.get("framework_manifest_id") != proposal_manifest.get("manifest_id"):
            raise InvalidTopology("Topology catalog mismatch")
        raw_edges = edge_manifest.get("edges")
        if not isinstance(raw_edges, list) or len(raw_edges) > 1500:
            raise InvalidTopology("Invalid edge catalogue")
        self.edges: dict[str, dict] = {}
        self.adj: dict[str, list[dict]] = {sid: [] for sid in self.nodes}
        for e in raw_edges:
            if not isinstance(e, dict):
                raise InvalidTopology("Invalid edge record")
            eid, src, dst = e.get("edge_id"), e.get("source_id"), e.get("target_id")
            sf, st = e.get("from_station"), e.get("to_station")
            if not all(_text(x) for x in (eid, src, dst, sf, st)) or eid in self.edges or src == dst:
                raise InvalidTopology("Invalid/duplicate directed edge")
            if src not in self.nodes or dst not in self.nodes:
                raise InvalidTopology("Unknown framework edge endpoint")
            if sf not in self.nodes[src]["knowledge_station_ids"] or st not in self.nodes[dst]["knowledge_station_ids"]:
                raise InvalidTopology("Station scope of edge is invalid")
            kind = "bridge" if sf != st else "road"
            if e.get("kind") != kind:
                raise InvalidTopology("Cross-station edge must be an explicit bridge")
            if e.get("qualification_state") not in STATES or e.get("authority_grant") is not False:
                raise InvalidTopology("Preview edges cannot grant authority")
            if not isinstance(e.get("hop_weight"), int) or isinstance(e.get("hop_weight"), bool) or not 1 <= e["hop_weight"] <= 9:
                raise InvalidTopology("Invalid conceptual hop weight")
            if kind == "bridge" and e.get("bridge_approved") is not False:
                raise InvalidTopology("Unqualified bridge cannot claim approval")
            if kind == "road" and e.get("bridge_approved") is not None:
                raise InvalidTopology("Road cannot impersonate a bridge")
            self.edges[eid] = e
            self.adj[src].append(e)
        for lst in self.adj.values():
            lst.sort(key=lambda e: e["edge_id"])

    def preview(self, source: str, destination: str, *, action: str = "browse.public",
                mode: str = "fewest-hops") -> RoutePreview:
        if action not in ALLOWED_ACTIONS:
            return RoutePreview("DENY", "ACTION_NOT_SUPPORTED")
        if not _text(source) or not _text(destination) or mode not in MODES:
            return RoutePreview("DENY", "INVALID_PUBLIC_ROUTE_REQUEST")
        if source not in self.nodes or destination not in self.nodes:
            return RoutePreview("HOLD", "FRAMEWORK_NOT_IN_PUBLIC_CATALOGUE")
        if source == destination:
            return RoutePreview("HOLD", "NO_TRAVERSAL_FOR_SAME_REFERENCE")
        # Dijkstra with deterministic order; costs are conceptual priorities only.
        # In fewer-bridges mode, cross-station transfers are penalized as review work.
        frontier: list[tuple[int, int, tuple[str, ...], str, tuple[str, ...], tuple[str, ...]]] = [
            (0, 0, (source,), source, (), ())]
        best: dict[str, tuple[int, int, tuple[str, ...]]] = {}
        chosen = None
        while frontier:
            cost, count, path, at, edges, edge_kinds = heapq.heappop(frontier)
            key = (cost, count, path)
            if at in best and best[at] <= key:
                continue
            best[at] = key
            if at == destination:
                chosen = (path, edges, edge_kinds)
                break
            for edge in self.adj[at]:
                nxt = edge["target_id"]
                if nxt in path:
                    continue
                bridge_penalty = 20 if mode == "fewer-bridges" and edge["kind"] == "bridge" else 0
                weight = 1 if mode == "fewest-hops" else edge["hop_weight"] + bridge_penalty
                heapq.heappush(frontier, (cost + weight, count + 1,
                                          path + (nxt,), nxt, edges + (edge["edge_id"],),
                                          edge_kinds + (edge["kind"],)))
        if chosen is None:
            return RoutePreview("HOLD", "NO_EXPLICIT_DIRECTED_REFERENCE_ROUTE")
        path, edges, _ = chosen
        hops = tuple((self.edges[e]["from_station"], self.edges[e]["to_station"]) for e in edges)
        needs = ["FRAMEWORK_REGISTRATIONS_UNVERIFIED", "SOURCE_ATTRIBUTION_UNVERIFIED",
                 "DIGITALME_MANDATE_UNVERIFIED", "WARDEN_NAVIGATION_POLICY_NOT_CONNECTED",
                 "RIVEROS_RECEIPT_NOT_CONNECTED", "DURABLE_REPLAY_NOT_ATTESTED",
                 "HUMAN_ADMISSION_REVIEW_MISSING"]
        if any(self.edges[e]["kind"] == "bridge" for e in edges):
            needs.append("CROSS_STATION_BRIDGES_UNQUALIFIED")
        if any(self.edges[e]["qualification_state"] != "CANDIDATE_FOR_REVIEW" for e in edges):
            needs.append("EDGE_QUALIFICATION_REQUIRED")
        payload = {"domain": "VSR-FOR-001-R0.9-PUBLIC-ROUTE",
                   "frameworks": [{"id": ref, "version": self.nodes[ref]["framework_version"]} for ref in path],
                   "edges": [{"id": e, "from": self.edges[e]["from_station"],
                              "to": self.edges[e]["to_station"],
                              "qualification": self.edges[e]["qualification_state"],
                              "kind": self.edges[e]["kind"],
                              "weight": self.edges[e]["hop_weight"]} for e in edges],
                   "mode": mode}
        route_hash = sha256(_canonical(payload)).hexdigest()
        return RoutePreview("REFERENCE_PREVIEW" if action == "browse.public" else "HOLD",
                            "PUBLIC_ONLY_NOT_ADMITTED" if action == "browse.public" else "LIVE_AUTHORITY_NOT_CONNECTED",
                            path, edges, hops, tuple(needs), route_hash)


def safe_public_summary(result: RoutePreview) -> dict:
    """Safe presentation of a local discovery, never a permit/token."""
    return {"status": result.disposition, "reason": result.reason,
            "framework_ids": list(result.references), "edge_ids": list(result.edge_ids),
            "station_hops": [list(x) for x in result.station_hops],
            "blockers": list(result.blockers), "public_route_digest": result.public_route_digest,
            "authority_granted": False, "engine_execution_allowed": False,
            "river_receipt_emitted": False, "registered_in_genesis": False,
            "deploy_allowed": False}