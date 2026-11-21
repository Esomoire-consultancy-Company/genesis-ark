"""R1.0 qualification-contract tests; proposals are not authoritative records."""
import copy
import json
from pathlib import Path
import unittest
from phase10_review_gate import evaluate, reviewer_packet

ROOT=Path(__file__).parent

def load(name):
    return json.loads((ROOT/name).read_text())


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.p=load('registration_proposals.json')
        self.e=load('phase9_proposed_edges.json')
        self.d=load('phase10_qualification_dossiers.json')
    def check(self, expected, edit=None, disposition='DENY'):
        if edit: edit()
        result=evaluate(self.p,self.e,self.d)
        self.assertEqual(result.reason,expected)
        self.assertEqual(result.disposition,disposition)
        self.assertFalse(result.registrar_authorized)
        self.assertFalse(result.warden_permit_granted)
        self.assertFalse(result.engine_execution_allowed)
        self.assertFalse(result.river_receipt_emitted)
        self.assertFalse(result.deployment_approved)
        return result
    def obj(self,id): return next(v for v in self.d['objects'] if v['framework_id']==id)
    def edge(self,id):return next(v for v in self.d['edges'] if v['edge_id']==id)
    def base_obj(self,id):return next(v for v in self.p['objects'] if v['source_framework_id']==id)
    def base_edge(self,id):return next(v for v in self.e['edges'] if v['edge_id']==id)

    def test_valid_dossier_review_only(self):
        result=self.check('METADATA_CONSISTENT_NOT_AUTHORITATIVELY_QUALIFIED',disposition='REVIEW_PACKET_READY_WITH_BLOCKERS')
        self.assertEqual((result.framework_count,result.edge_count),(14,13))
        self.assertEqual((result.citation_identified,result.citation_missing),(9,5))
        self.assertEqual((result.pending_object_reviews,result.pending_edge_reviews),(14,13))
        self.assertEqual(len(result.review_blockers),5)
    def test_packet_contains_no_signoff(self):
        result=evaluate(self.p,self.e,self.d)
        packet=reviewer_packet(result)
        self.assertEqual(packet['status'],'HUMAN_REVIEW_REQUIRED')
        self.assertIsNone(packet['reviewer_id'])
        self.assertIsNone(packet['signature'])
        self.assertFalse(packet['verified'])
        self.assertFalse(packet['authority_granted'])
    def test_invalid_packet_fail_closed(self):
        self.d['status']='ACTIVE'
        self.assertEqual(reviewer_packet(evaluate(self.p,self.e,self.d))['status'],'HOLD')
    def test_dossier_digest_stable(self):
        first=evaluate(self.p,self.e,self.d).evidence_digest
        second=evaluate(copy.deepcopy(self.p),copy.deepcopy(self.e),copy.deepcopy(self.d)).evidence_digest
        self.assertEqual(first,second)
    def test_attribution_change_rebinds_digest(self):
        first=evaluate(self.p,self.e,self.d).evidence_digest
        self.obj('FOR-0001')['attribution_note']+=' Added uncertainty.'
        self.assertNotEqual(first,evaluate(self.p,self.e,self.d).evidence_digest)
    def test_edge_review_condition_changes_digest(self):
        first=evaluate(self.p,self.e,self.d).evidence_digest
        self.edge('QNT-01')['review_condition']+=' another caveat'
        self.assertNotEqual(first,evaluate(self.p,self.e,self.d).evidence_digest)
    def test_non_mapping_fail(self):
        self.assertEqual(evaluate({},self.e,self.d).reason,'AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    def test_base_registration_forgery(self):
        self.p['registration_count']=1
        self.check('AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    def test_base_registration_action_not_allowed(self):
        self.p['registration_action_requested']=True
        self.check('AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    def test_dossier_status_must_stay_review_only(self):
        self.d['status']='REGISTERED'
        self.check('AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    def test_topology_grants_forbidden(self):
        self.e['authority_grants']=1
        self.check('AUTHORITY_OR_REGISTRATION_STATUS_FORBIDDEN')
    def test_wrong_source_lineage_denied(self):
        self.d['source_framework_manifest_id']='unknown'
        self.check('MANIFEST_LINEAGE_MISMATCH')
    def test_wrong_edge_lineage_denied(self):
        self.d['source_edges_manifest_id']='unknown'
        self.check('MANIFEST_LINEAGE_MISMATCH')
    def test_object_count_mismatch(self):
        self.d['object_count']=15
        self.check('MANIFEST_COUNT_MISMATCH')
    def test_edge_count_mismatch(self):
        self.d['edge_count']=14
        self.check('MANIFEST_COUNT_MISMATCH')
    def test_missing_framework_dossier(self):
        self.d['objects'].pop()
        self.d['object_count']-=1
        self.check('MANIFEST_COUNT_MISMATCH')
    def test_duplicate_framework_dossier(self):
        self.d['objects'][-1]=self.d['objects'][0]
        self.check('MISSING_DUPLICATE_OR_EXTRA_DOSSIER')
    def test_extra_fabricated_framework(self):
        item=copy.deepcopy(self.d['objects'][0]);item['framework_id']='FOR-9999'
        self.d['objects'].append(item);self.d['object_count']+=1
        self.check('MANIFEST_COUNT_MISMATCH')
    def test_duplicate_edge_dossier(self):
        self.d['edges'][-1]=self.d['edges'][0]
        self.check('MISSING_DUPLICATE_OR_EXTRA_DOSSIER')
    def test_base_fake_id_denied(self):
        self.base_obj('FOR-0001')['external_registry_id']='LIVE-FAKE'
        self.check('BASE_REGISTRATION_OR_AUTHORITY_FORBIDDEN')
    def test_base_engine_execution_denied(self):
        self.base_obj('FOR-0002')['engine_execution_authorized']=True
        self.check('BASE_REGISTRATION_OR_AUTHORITY_FORBIDDEN')
    def test_invalid_origin_class(self):
        self.obj('FOR-0007')['origin_class']='FABRICATED_DISCOVERY'
        self.check('ORIGIN_CLASS_INVALID')
    def test_author_credit_wrong_type(self):
        self.obj('FOR-0010')['author_credit']='Einstein'
        self.check('AUTHOR_CREDIT_INVALID')
    def test_author_credit_duplicate(self):
        self.obj('FOR-0010')['author_credit'].append('Albert Einstein')
        self.check('AUTHOR_CREDIT_INVALID')
    def test_source_url_insecure(self):
        self.obj('FOR-0010')['source_urls']=['http://example.org/paper']
        self.check('SOURCE_URL_INVALID')
    def test_source_url_local_ip(self):
        self.obj('FOR-0010')['source_urls']=['https://127.0.0.1/paper']
        self.check('SOURCE_URL_INVALID')
    def test_source_url_local_network(self):
        self.obj('FOR-0010')['source_urls']=['https://localhost.local/paper']
        self.check('SOURCE_URL_INVALID')
    def test_source_url_duplicate(self):
        self.obj('FOR-0010')['source_urls']*=2
        self.check('SOURCE_URL_INVALID')
    def test_missing_primary_author(self):
        self.obj('FOR-0010')['author_credit']=[]
        self.check('NAMED_PRIMARY_SOURCE_MISSING_CREDIT')
    def test_missing_primary_source(self):
        self.obj('FOR-0010')['source_urls']=[]
        self.obj('FOR-0010')['source_review_status']='SOURCE_IDENTIFICATION_REQUIRED'
        self.check('NAMED_PRIMARY_SOURCE_MISSING_CREDIT')
    def test_internal_originator_not_assumed(self):
        self.obj('FOR-0005')['author_credit']=['Unknown invented person']
        self.check('INTERNAL_ORIGINATOR_UNATTESTED')
    def test_source_status_with_url_mismatch(self):
        self.obj('FOR-0002')['source_review_status']='SOURCE_IDENTIFICATION_REQUIRED'
        self.check('SOURCE_REVIEW_STATE_CONTRADICTION')
    def test_source_status_without_url_mismatch(self):
        self.obj('FOR-0005')['source_review_status']='CITATION_IDENTIFIED_UNAUDITED'
        self.check('SOURCE_REVIEW_STATE_CONTRADICTION')
    def test_fake_completed_rights_review(self):
        self.obj('FOR-0001')['rights_review']='APPROVED'
        self.check('UNVERIFIED_QUALIFICATION_CLAIM')
    def test_fake_technical_qualification(self):
        self.obj('FOR-0013')['technical_qualification']='VERIFIED'
        self.check('UNVERIFIED_QUALIFICATION_CLAIM')
    def test_fake_registrar_authorization(self):
        self.obj('FOR-0013')['genesis_registration_authorized']=True
        self.check('UNVERIFIED_QUALIFICATION_CLAIM')
    def test_fake_scientific_execution(self):
        self.obj('FOR-0012')['execution_qualified']=True
        self.check('UNVERIFIED_QUALIFICATION_CLAIM')
    def test_missing_applicability(self):
        self.obj('FOR-0007')['applicability_conditions']=[]
        self.check('APPLICABILITY_OR_ATTRIBUTION_MISSING')
    def test_missing_limitation(self):
        self.obj('FOR-0012')['non_applicability']=[]
        self.check('APPLICABILITY_OR_ATTRIBUTION_MISSING')
    def test_edge_invalid_class(self):
        self.edge('VIL-01')['relationship_class']='PROVEN_SCIENTIFIC_DERIVATION'
        self.check('EDGE_RELATIONSHIP_CLASS_INVALID')
    def test_qnt_01_is_not_causal_derivation(self):
        self.edge('QNT-01')['relationship_class']='ENGINEERING_HANDOFF'
        self.check('QUANTUM_LINK_WRONGLY_FRAMED_AS_DERIVATION')
    def test_qnt_02_is_not_causal_derivation(self):
        self.edge('QNT-02')['relationship_class']='WORKFLOW_SEQUENCE'
        self.check('QUANTUM_LINK_WRONGLY_FRAMED_AS_DERIVATION')
    def test_unqualified_edge_cannot_claim_approved(self):
        self.edge('QNT-02')['review_status']='QUALIFIED'
        self.check('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
    def test_unqualified_edge_cannot_claim_auth(self):
        self.edge('VIL-01')['auth_grant']=True
        self.check('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
    def test_unqualified_edge_cannot_claim_derivation(self):
        self.edge('QNT-01')['scientific_derivation_claim']=True
        self.check('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
    def test_unqualified_bridge_cannot_claim_approved(self):
        self.edge('BUF-03')['bridge_approved']=True
        self.check('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
    def test_unqualified_edge_cannot_execute(self):
        self.edge('VIL-01')['engine_execution_allowed']=True
        self.check('EDGE_UNVERIFIED_AUTHORITY_OR_DERIVATION_CLAIM')
    def test_base_edge_qualification_cannot_be_forged(self):
        self.base_edge('BUF-01')['qualification_state']='QUALIFIED'
        self.check('BASE_EDGE_ALREADY_CLAIMS_QUALIFICATION')
    def test_base_bridge_approval_cannot_be_forged(self):
        self.base_edge('ALT-01')['bridge_approved']=True
        self.check('BASE_EDGE_ALREADY_CLAIMS_QUALIFICATION')
    def test_missing_edge_review_condition(self):
        self.edge('VIL-02')['review_condition']=''
        self.check('EDGE_CLAIM_OR_REVIEW_GATE_MISSING')
    def test_malformed_edge_list(self):
        self.d['edges']=None
        self.check('OBJECT_OR_EDGE_LIST_MISSING')

if __name__=='__main__':unittest.main()