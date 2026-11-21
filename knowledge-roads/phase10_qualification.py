"""VSR-FOR-001 R0.10: provenance and qualification dossier lint.

This tool validates proposal-only metadata. It has no network access, trusted
source validation, registry write, Warden policy evaluation, or RiverOS writer.
Even a structurally complete packet is never an approved framework.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class QualificationReport:
    disposition: str
    reason: str
    framework_count: int = 0
    edge_count: int = 0
    source_reference_count: int = 0
    sources_without_references: tuple[str, ...] = ()
    conceptual_bridges: tuple[str, ...] = ()
    reviewed_qualified_count: int = 0
    fingerprint: str | None = None
    genesis_registration_allowed: bool = False
    warden_navigation_allowed: bool = False
    engine_execution_allowed: bool = False
    river_receipt_emitted: bool = False
    publish_approved: bool = False


class QualificationError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2048


def _idset(items: Any, key: str) -> set[str]:
    if not isinstance(items, list):
        raise QualificationError("INVALID_RECORD_COLLECTION")
    seen: set[str] = set()
    for record in items:
        if not isinstance(record, dict) or not _text(record.get(key)):
            raise QualificationError("INVALID_RECORD_ID")
        if record[key] in seen:
            raise QualificationError("DUPLICATE_RECORD_ID")
        seen.add(record[key])
    return seen


def _safe_source(url: Any) -> bool:
    if not _text(url):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname is not None
                and parts.hostname not in {"localhost", "127.0.0.1", "0.0.0.0"}
                and parts.username is None and parts.password is None
                and parts.fragment == "" and parts.port in (None, 443))
    except (ValueError, TypeError):
        return False


def audit_qualification(
    proposals: Mapping[str, Any],
    topology: Mapping[str, Any],
    dossiers: Mapping[str, Any],
) -> QualificationReport:
    """Fail closed on schema and provenance mismatches; HOLD even if valid."""
    def fail(reason: str) -> QualificationReport:
        return QualificationReport("DENY", reason)

    if not all(isinstance(x, Mapping) for x in (proposals, topology, dossiers)):
        return fail("MALFORMED_INPUT")
    if (proposals.get("status") != "PROPOSAL_ONLY_NOT_REGISTERED"
            or proposals.get("registration_count") != 0
            or proposals.get("registration_action_requested") is not False
            or topology.get("status") != "PROPOSED_ONLY_NO_AUTHORITY"
            or topology.get("authority_grants") != 0
            or dossiers.get("status") != "SOURCE_AND_EDGE_REVIEW_ONLY"):
        return fail("PROPOSAL_ONLY_STATE_REQUIRED")
    if (topology.get("framework_manifest_id") != proposals.get("manifest_id")
            or dossiers.get("source_framework_manifest_id") != proposals.get("manifest_id")
            or dossiers.get("source_edges_manifest_id") != topology.get("manifest_id")):
        return fail("SOURCE_MANIFEST_BINDING_MISMATCH")
    try:
        node_ids = _idset(proposals.get("objects"), "source_framework_id")
        edge_ids = _idset(topology.get("edges"), "edge_id")
        node_review_ids = _idset(dossiers.get("objects"), "framework_id")
        edge_review_ids = _idset(dossiers.get("edges"), "edge_id")
    except QualificationError as exc:
        return fail(str(exc))
    if not node_ids or not edge_ids or node_ids != node_review_ids or edge_ids != edge_review_ids:
        return fail("INCOMPLETE_DOSSIER_COVERAGE")
    if (dossiers.get("object_count") != len(node_ids)
            or dossiers.get("edge_count") != len(edge_ids)):
        return fail("DOSSIER_COUNTS_MISMATCH")

    nodes = {o["source_framework_id"]: o for o in proposals["objects"]}
    edges = {o["edge_id"]: o for o in topology["edges"]}
    needs_sources: list[str] = []
    reference_count = 0
    for dossier in dossiers["objects"]:
        fid = dossier["framework_id"]
        proposal = nodes[fid]
        if (proposal.get("registration_state") != "PROPOSED_LOCAL_ONLY"
                or proposal.get("external_registry_id") is not None
                or proposal.get("engine_execution_authorized") is not False
                or proposal.get("authority_grant") is not False):
            return fail("PROPOSAL_REGISTRATION_OR_AUTHORITY_ESCALATION")
        if (dossier.get("original_attribution_approved") is not False
                or dossier.get("genesis_registration_authorized") is not False
                or dossier.get("execution_qualified") is not False
                or dossier.get("rights_review") != "NOT_COMPLETED"
                or dossier.get("technical_qualification") != "NOT_COMPLETED"):
            return fail("FALSE_REVIEW_OR_AUTHORITY_CLAIM")
        if (not _text(dossier.get("origin_class"))
                or not _text(dossier.get("attribution_note"))
                or not _text(dossier.get("original_author_claim_type"))):
            return fail("INCOMPLETE_ATTRIBUTION_RECORD")
        authors = dossier.get("author_credit")
        if not isinstance(authors, list) or any(not _text(a) for a in authors):
            return fail("INVALID_AUTHOR_CREDIT")
        if dossier["origin_class"] == "PRIMARY_SCIENTIFIC_PUBLICATION" and not authors:
            return fail("PRIMARY_PUBLICATION_MISSING_AUTHORS")
        if dossier.get("original_author_claim_type") == "NAMED_CREDIT_NOT_OWNERSHIP" and not authors:
            return fail("AUTHOR_CREDIT_CLAIM_MISMATCH")
        if (not isinstance(dossier.get("applicability_conditions"), list)
                or not dossier["applicability_conditions"]
                or any(not _text(s) for s in dossier["applicability_conditions"])
                or not isinstance(dossier.get("non_applicability"), list)
                or not dossier["non_applicability"]
                or any(not _text(s) for s in dossier["non_applicability"])):
            return fail("MISSING_APPLICABILITY_OR_LIMITS")
        urls = dossier.get("source_urls")
        if not isinstance(urls, list) or len(set(map(str, urls))) != len(urls):
            return fail("INVALID_SOURCE_LIST")
        if any(not _safe_source(u) for u in urls):
            return fail("UNSAFE_SOURCE_REFERENCE")
        expected = "CITATION_IDENTIFIED_UNAUDITED" if urls else "SOURCE_IDENTIFICATION_REQUIRED"
        if dossier.get("source_review_status") != expected:
            return fail("UNSUPPORTED_SOURCE_REVIEW_CLAIM")
        reference_count += len(urls)
        if not urls:
            needs_sources.append(fid)
        if (set(proposal.get("transport_roles", [])) & {"engine"}
                and proposal.get("engine_qualification") not in ("LOCAL_DEMONSTRATOR_ONLY", "NONE")):
            return fail("UNREVIEWED_ENGINE_QUALIFICATION_CLAIM")

    conceptual_bridges: list[str] = []
    for dossier in dossiers["edges"]:
        eid = dossier["edge_id"]
        edge = edges[eid]
        if (edge.get("qualification_state") != "PROPOSED_ONLY"
                or edge.get("authority_grant") is not False
                or edge.get("kind") not in {"road", "bridge"}):
            return fail("EDGE_ESCALATION_IN_SOURCE_TOPOLOGY")
        if (dossier.get("review_status") != "UNQUALIFIED_PROPOSAL"
                or dossier.get("scientific_derivation_claim") is not False
                or dossier.get("technical_review_completed") is not False
                or dossier.get("bridge_approved") is not False
                or dossier.get("auth_grant") is not False
                or dossier.get("engine_execution_allowed") is not False):
            return fail("FALSE_EDGE_QUALIFICATION_OR_AUTHORITY")
        if (not _text(dossier.get("relationship_class"))
                or not _text(dossier.get("semantic_claim"))
                or not _text(dossier.get("review_condition"))):
            return fail("EDGE_REVIEW_INCOMPLETE")
        if edge["kind"] == "bridge":
            conceptual_bridges.append(eid)
            if edge.get("bridge_approved") is not False:
                return fail("UNQUALIFIED_BRIDGE_APPROVAL")
        if eid.startswith("QNT-") and dossier["relationship_class"] not in {
            "PEDAGOGICAL_SEQUENCE_NOT_DERIVATION", "GOVERNANCE_HANDOFF"
        }:
            return fail("QUANTUM_RESEARCH_RELATIONSHIP_MISCLASSIFIED")

    try:
        fingerprint = sha256(_canon({
            "domain": "VSR-FOR-001-R10-REVIEW_ONLY",
            "proposal": proposals,
            "edges": topology,
            "dossiers": dossiers,
        })).hexdigest()
    except (TypeError, ValueError):
        return fail("UNSERIALIZABLE_DOSSIER")
    return QualificationReport(
        disposition="HOLD",
        reason="UNATTESTED_SOURCES_AND_UNQUALIFIED_TRANSITIONS",
        framework_count=len(node_ids), edge_count=len(edge_ids),
        source_reference_count=reference_count,
        sources_without_references=tuple(sorted(needs_sources)),
        conceptual_bridges=tuple(sorted(conceptual_bridges)),
        reviewed_qualified_count=0, fingerprint=fingerprint,
    )
