"""VSR-FOR-001 R1.0: non-authorizing source/edge qualification review.

Validates attribution dossiers against the earlier *provisional* framework and
edge manifests. It produces a review packet, never admission or registrations.
It does not fetch sources or impersonate reviewers.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import ipaddress
import json
from typing import Any, Mapping
from urllib.parse import urlsplit

ORIGIN_CLASSES = frozenset({
    'EVOLVED_STRATEGY_METHOD', 'NAMED_MATHEMATICAL_THEOREM',
    'GENERAL_RESEARCH_METHOD', 'GENERAL_FINANCIAL_METHOD',
    'INTERNAL_WORKFLOW_PATTERN', 'INTERNAL_CHANGE_WORKFLOW',
    'GENERAL_CONSERVATION_PRINCIPLE', 'GENERAL_CONTROL_THEORY_CONCEPT',
    'GENERAL_CONTROL_TECHNIQUE', 'PRIMARY_SCIENTIFIC_PUBLICATION',
    'GENERAL_MATHEMATICAL_CLASS',
})
EDGE_CLASSES = frozenset({
    'WORKFLOW_SEQUENCE', 'GOVERNANCE_HANDOFF', 'EVIDENCE_HANDOFF',
    'ENGINEERING_HANDOFF', 'PEDAGOGICAL_SEQUENCE_NOT_DERIVATION',
    'CROSS_DOMAIN_ANALOGY',
})
SOURCE_STATES = frozenset({'CITATION_IDENTIFIED_UNAUDITED','SOURCE_IDENTIFICATION_REQUIRED'})
INTERNAL_CLASSES = frozenset({'INTERNAL_WORKFLOW_PATTERN','INTERNAL_CHANGE_WORKFLOW'})
PRIMARY_CLASSES = frozenset({'PRIMARY_SCIENTIFIC_PUBLICATION','NAMED_MATHEMATICAL_THEOREM'})


def _txt(x: Any) -> bool:
    return isinstance(x,str) and bool(x.strip()) and len(x)<=1000


def _source_url(s: Any) -> bool:
    if not isinstance(s,str) or len(s)>2048: return False
    try:
        p=urlsplit(s)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
            return False
        if p.fragment: return False
        try:
            ipaddress.ip_address(p.hostname)
            return False
        except ValueError: pass
        return '.' in p.hostname and not p.hostname.endswith(('.local','.internal','.localhost'))
    except ValueError:
        return False


def _digest(record: Mapping[str,Any]) -> str:
    return sha256(json.dumps(record,sort_keys=True,ensure_ascii=False,
      separators=(',',':'),allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ReviewResult:
    disposition: str
    reason: str
    framework_count: int=0
    edge_count: int=0
    citation_identified: int=0
    citation_missing: int=0
    pending_object_reviews: int=0
    pending_edge_reviews: int=0
    evidence_digest: str|None=None
    review_blockers: tuple[str,...]=()
    registrar_authorized: bool=False
    warden_permit_granted: bool=False
    engine_execution_allowed: bool=False
    river_receipt_emitted: bool=False
    deployment_approved: bool=False


def evaluate(proposals: Mapping[str,Any], topology: Mapping[str,Any], dossier: Mapping[str,Any]) -> ReviewResult:
    """Fail closed. Passing schema checks never qualifies frameworks or routes."""
    def stop(reason: str, kind: str='DENY') -> ReviewResult: return ReviewResult(kind,reason)
    if not all(isinstance(v,Mapping) for v in (proposals,topology,dossier)):
        return stop('NON_MAPPING_MANIFEST')
    if (proposals.get('status')!='PROPOSAL_ONLY_NOT_REGISTERED'
          or proposals.get('registration_count')!=0
          or proposals.get('registration_action_requested') is not False
          or topology.get('status')!='PROPOSED_ONLY_NO_AUTHORITY'
          or topology.get('authority_grants')!=0
          or dossier.get('status')!='SOURCE_AND_EDGE_REVIEW_ONLY'):
        return stop('AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    if (dossier.get('source_framework_manifest_id')!=proposals.get('manifest_id')
          or dossier.get('source_edges_manifest_id')!=topology.get('manifest_id')
          or topology.get('framework_manifest_id')!=proposals.get('manifest_id')):
        return stop('MANIFEST_LINEAGE_MISMATCH')
    objects,edges = proposals.get('objects'),topology.get('edges')
    d_objects,d_edges=dossier.get('objects'),dossier.get('edges')
    if not (isinstance(objects,list) and isinstance(edges,list)
      and isinstance(d_objects,list) and isinstance(d_edges,list)):
        return stop('OBJECT_OR_EDGE_LIST_MISSING')
    if not (0<len(objects)<=250 and len(edges)<=1500): return stop('OBJECT_OR_EDGE_LIMIT')
    if dossier.get('object_count')!=len(objects) or dossier.get('edge_count')!=len(edges):
        return stop('MANIFEST_COUNT_MISMATCH')
    source_ids=[x.get('source_framework_id') for x in objects if isinstance(x,Mapping)]
    edge_ids=[x.get('edge_id') for x in edges if isinstance(x,Mapping)]
    dossier_ids=[x.get('framework_id') for x in d_objects if isinstance(x,Mapping)]
    dossier_edges=[x.get('edge_id') for x in d_edges if isinstance(x,Mapping)]
    if (len(source_ids)!=len(objects) or len(edge_ids)!=len(edges)
      or len(dossier_ids)!=len(d_objects) or len(dossier_edges)!=len(d_edges)
      or not all(_txt(x) for x in source_ids+edge_ids+dossier_ids+dossier_edges)
      or len(set(source_ids))!=len(source_ids) or len(set(edge_ids))!=len(edge_ids)
      or len(set(dossier_ids))!=len(dossier_ids) or len(set(dossier_edges))!=len(dossier_edges)
      or set(source_ids)!=set(dossier_ids) or set(edge_ids)!=set(dossier_edges)):
        return stop('MISSING_DUPLICATE_OR_EXTRA_DOSSIER')
    if len(d_objects)!=len(objects) or len(d_edges)!=len(edges):
        return stop('DOSSIER_CARDINALITY_MISMATCH')
    originals={x['source_framework_id']:x for x in objects}
    physical_edges={x['edge_id']:x for x in edges}
    citation_identified=0
    citation_missing=0
    for r in d_objects:
        base=originals[r['framework_id']]
        if (base.get('registration_state')!='PROPOSED_LOCAL_ONLY'
             or base.get('external_registry_id') is not None
             or base.get('authority_grant') is not False
             or base.get('engine_execution_authorized') is not False):
            return stop('BASE_REGISTRATION_OR_AUTHORITY_FORBIDDEN')
        if r.get('origin_class') not in ORIGIN_CLASSES:
            return stop('ORIGIN_CLASS_INVALID')
        author_credit=r.get('author_credit')
        urls=r.get('source_urls')
        if (not isinstance(author_credit,list) or not all(_txt(a) for a in author_credit)
             or len(set(author_credit))!=len(author_credit)):
            return stop('AUTHOR_CREDIT_INVALID')
        if (not isinstance(urls,list) or any(not _source_url(u) for u in urls)
             or len(set(urls))!=len(urls)):
            return stop('SOURCE_URL_INVALID')
        if r.get('source_review_status') not in SOURCE_STATES:
            return stop('SOURCE_REVIEW_STATE_FORBIDDEN')
        if not (isinstance(r.get('applicability_conditions'),list)
          and isinstance(r.get('non_applicability'),list)
          and len(r['applicability_conditions'])>=1 and len(r['non_applicability'])>=1
          and all(_txt(v) for v in r['applicability_conditions']+r['non_applicability'])
          and _txt(r.get('attribution_note'))):
            return stop('APPLICABILITY_OR_ATTRIBUTION_MISSING')
        if (r.get('rights_review')!='NOT_COMPLETED'
          or r.get('technical_qualification')!='NOT_COMPLETED'
          or r.get('original_attribution_approved') is not False
          or r.get('genesis_registration_authorized') is not False
          or r.get('execution_qualified') is not False):
            return stop('UNVERIFIED_QUALIFICATION_CLAIM')
        if r['origin_class'] in PRIMARY_CLASSES and (not author_credit or not urls):
            return stop('NAMED_PRIMARY_SOURCE_MISSING_CREDIT')
        if r['origin_class'] in INTERNAL_CLASSES and author_credit:
            return stop('INTERNAL_ORIGINATOR_UNATTESTED')
        if (urls and r['source_review_status']!='CITATION_IDENTIFIED_UNAUDITED'
          or not urls and r['source_review_status']!='SOURCE_IDENTIFICATION_REQUIRED'):
            return stop('SOURCE_REVIEW_STATE_CONTRADICTION')
        citation_identified+=bool(urls)
        citation_missing+=not bool(urls)
    for r in d_edges:
        e=physical_edges[r['edge_id']]
        if (e.get('qualification_state')!='PROPOSED_ONLY'
             or e.get('authority_grant') is not False
             or e.get('kind') not in ('road','bridge')
             or e.get('bridge_approved') is not (False if e['kind']=='bridge' else None)):
            return stop('BASE_EDGE_ALREADY_CLAIMS_QUALIFICATION')
        if r.get('relationship_class') not in EDGE_CLASSES:
            return stop('EDGE_RELATIONSHIP_CLASS_INVALID')
        if not _txt(r.get('semantic_claim')) or not _txt(r.get('review_condition')):
            return stop('EDGE_CLAIM_OR_REVIEW_GATE_MISSING')
        if (r.get('review_status')!='UNQUALIFIED_PROPOSAL'
            or r.get('scientific_derivation_claim') is not False
            or r.get('technical_review_completed') is not False
            or r.get('bridge_approved') is not False
            or r.get('auth_grant') is not False
            or r.get('engine_execution_allowed') is not False):
            return stop('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
        if (r['edge_id'] in ('QNT-01','QNT-02')
             and r['relationship_class']!='PEDAGOGICAL_SEQUENCE_NOT_DERIVATION'):
            return stop('QUANTUM_LINK_WRONGLY_FRAMED_AS_DERIVATION')
    digest=_digest({'catalogue_id':proposals['manifest_id'],'edges_id':topology['manifest_id'],
      'dossier_id':dossier.get('manifest_id'), 'objects':d_objects,'edges':d_edges})
    blockers=(
      'CITATION_AUDIT_OR_SOURCE_IDENTIFICATION_PENDING',
      'FRAMEWORK_ORIGIN_RIGHTS_AND_APPLICABILITY_REVIEW_PENDING',
      'ALL_13_EDGE_REVIEW_AND_CROSS_STATION_BRIDGE_QUALIFICATION_PENDING',
      'NO_AUTHORIZED_GENESIS_REGISTRAR_OR_WARDEN_ADMISSION',
      'NO_AUTHENTIC_DIGITALME_OR_RIVER_EVIDENCE',
    )
    return ReviewResult('REVIEW_PACKET_READY_WITH_BLOCKERS',
      'METADATA_CONSISTENT_NOT_AUTHORITATIVELY_QUALIFIED',len(objects),len(edges),
      citation_identified,citation_missing,len(d_objects),len(d_edges),digest,blockers)


def reviewer_packet(result: ReviewResult) -> dict[str,Any]:
    """Generic human review checklist with zero preassigned authority."""
    if result.disposition!='REVIEW_PACKET_READY_WITH_BLOCKERS':
        return {'status':'HOLD','reason':'QUALIFICATION_MANIFEST_INVALID','entries':[]}
    return {
      'status':'HUMAN_REVIEW_REQUIRED','evidence_digest':result.evidence_digest,
      'counts':{'frameworks':result.framework_count,'edges':result.edge_count,
        'source_identified':result.citation_identified,'source_missing':result.citation_missing},
      'review_gates':['original_name_and_attribution','source_retrieval_and_license',
        'scope_applicability_and_limitations','independent_edge_semantics',
        'bridge_scope_and_owner','signed_human_review','Genesis_registration_separately_authorized',
        'Warden_navigation_policy_separately_admitted'],
      'signature':None,'reviewer_id':None,'verified':False,
      'authority_granted':False,'engine_execution_allowed':False,'river_receipt_emitted':False,
    }