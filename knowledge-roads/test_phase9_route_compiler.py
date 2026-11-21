"""R0.9 public knowledge-navigation and hard authority-boundary tests."""
import copy
import json
from pathlib import Path
import unittest
from phase9_route_compiler import PreviewGraph, InvalidTopology, safe_public_summary

HERE = Path(__file__).parent


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.frameworks = json.loads((HERE / 'registration_proposals.json').read_text())
        self.edges = json.loads((HERE / 'phase9_proposed_edges.json').read_text())
        self.graph = PreviewGraph(self.frameworks, self.edges)

    def test_14_source_objects(self):
        self.assertEqual(len(self.graph.nodes), 14)

    def test_13_explicit_edges(self):
        self.assertEqual(len(self.graph.edges), 13)

    def test_village_route_public_preview(self):
        r = self.graph.preview('FOR-0001', 'FOR-0004')
        self.assertEqual(r.disposition, 'REFERENCE_PREVIEW')
        self.assertEqual(r.references, ('FOR-0001','FOR-0003','FOR-0004'))

    def test_buffet_route(self):
        r = self.graph.preview('FOR-0008','FOR-0005')
        self.assertEqual(r.references,('FOR-0008','FOR-0007','FOR-0009','FOR-0005'))
        self.assertIn('CROSS_STATION_BRIDGES_UNQUALIFIED',r.blockers)

    def test_quantum_research_is_not_executable(self):
        r = self.graph.preview('FOR-0010','FOR-0012')
        self.assertEqual(r.references,('FOR-0010','FOR-0011','FOR-0012'))
        self.assertFalse(r.engine_execution_allowed)

    def test_distributed_system_bridge_unqualified(self):
        r=self.graph.preview('FOR-0013','FOR-0009')
        self.assertIn('CROSS_STATION_BRIDGES_UNQUALIFIED',r.blockers)
        self.assertEqual(r.station_hops,(('VSR-KS-DISTRIBUTED_SYSTEMS','VSR-KS-ENGINEERING'),))

    def test_same_station_does_not_imply_edge(self):
        r=self.graph.preview('FOR-0007','FOR-0008')
        self.assertEqual(r.reason,'NO_EXPLICIT_DIRECTED_REFERENCE_ROUTE')

    def test_reverse_road_not_assumed(self):
        self.assertEqual(self.graph.preview('FOR-0003','FOR-0001').disposition,'HOLD')

    def test_no_self_route_as_authority(self):
        self.assertEqual(self.graph.preview('FOR-0001','FOR-0001').reason,'NO_TRAVERSAL_FOR_SAME_REFERENCE')

    def test_unknown_endpoint_hold(self):
        self.assertEqual(self.graph.preview('FOR-NOT-FOUND','FOR-0002').disposition,'HOLD')

    def test_unknown_action_denied(self):
        self.assertEqual(self.graph.preview('FOR-0001','FOR-0003',action='engine.execute').disposition,'DENY')

    def test_protected_navigation_is_hold_even_with_path(self):
        r=self.graph.preview('FOR-0001','FOR-0003',action='navigate.readonly')
        self.assertEqual(r.disposition,'HOLD')
        self.assertEqual(r.reason,'LIVE_AUTHORITY_NOT_CONNECTED')
        self.assertFalse(r.authority_granted)

    def test_fastest_hops_route_prefers_two_bridges(self):
        r=self.graph.preview('FOR-0001','FOR-0006',mode='fewest-hops')
        self.assertEqual(r.references,('FOR-0001','FOR-0009','FOR-0006'))
        self.assertEqual(len(r.station_hops),2)

    def test_assurance_mode_prefers_fewer_bridges(self):
        r=self.graph.preview('FOR-0001','FOR-0006',mode='fewer-bridges')
        self.assertEqual(r.references,('FOR-0001','FOR-0003','FOR-0004','FOR-0005','FOR-0006'))

    def test_modes_produce_different_hashes(self):
        a=self.graph.preview('FOR-0001','FOR-0006',mode='fewest-hops')
        b=self.graph.preview('FOR-0001','FOR-0006',mode='fewer-bridges')
        self.assertNotEqual(a.public_route_digest,b.public_route_digest)

    def test_repeatability(self):
        a=self.graph.preview('FOR-0001','FOR-0006')
        b=self.graph.preview('FOR-0001','FOR-0006')
        self.assertEqual(a.public_route_digest,b.public_route_digest)

    def test_digest_changes_with_framework_version(self):
        n=copy.deepcopy(self.frameworks)
        n['objects'][0]['framework_version']='0.2.0'
        self.assertNotEqual(self.graph.preview('FOR-0001','FOR-0006').public_route_digest,
                            PreviewGraph(n,self.edges).preview('FOR-0001','FOR-0006').public_route_digest)

    def test_digest_changes_with_edge_weight(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['hop_weight']=9
        self.assertNotEqual(self.graph.preview('FOR-0001','FOR-0004').public_route_digest,
                            PreviewGraph(self.frameworks,e).preview('FOR-0001','FOR-0004').public_route_digest)

    def test_digest_changes_with_edge_qualification(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['qualification_state']='CANDIDATE_FOR_REVIEW'
        self.assertNotEqual(self.graph.preview('FOR-0001','FOR-0004').public_route_digest,
                            PreviewGraph(self.frameworks,e).preview('FOR-0001','FOR-0004').public_route_digest)

    def test_summary_discloses_no_permits(self):
        s=safe_public_summary(self.graph.preview('FOR-0001','FOR-0006'))
        self.assertEqual(set(s), {'status','reason','framework_ids','edge_ids','station_hops','blockers','public_route_digest','authority_granted','engine_execution_allowed','river_receipt_emitted','registered_in_genesis','deploy_allowed'})
        self.assertTrue(all(s[k] is False for k in ('authority_granted','engine_execution_allowed','river_receipt_emitted','registered_in_genesis','deploy_allowed')))

    def test_missing_provenance_blocks_every_route(self):
        r=self.graph.preview('FOR-0001','FOR-0003')
        self.assertIn('SOURCE_ATTRIBUTION_UNVERIFIED',r.blockers)
        self.assertIn('FRAMEWORK_REGISTRATIONS_UNVERIFIED',r.blockers)

    def test_unqualified_roads_stay_unqualified(self):
        self.assertIn('EDGE_QUALIFICATION_REQUIRED',self.graph.preview('FOR-0001','FOR-0003').blockers)

    def test_spoofed_active_catalogue_rejected(self):
        n=copy.deepcopy(self.frameworks)
        n['objects'][0]['registration_state']='ACTIVE'
        with self.assertRaises(InvalidTopology): PreviewGraph(n,self.edges)

    def test_false_registration_count_rejected(self):
        n=copy.deepcopy(self.frameworks)
        n['registration_count']=1
        with self.assertRaises(InvalidTopology): PreviewGraph(n,self.edges)

    def test_fake_authority_rejected(self):
        n=copy.deepcopy(self.frameworks)
        n['objects'][0]['authority_grant']=True
        with self.assertRaises(InvalidTopology): PreviewGraph(n,self.edges)

    def test_production_engine_claim_rejected(self):
        n=copy.deepcopy(self.frameworks)
        n['objects'][0]['engine_execution_authorized']=True
        with self.assertRaises(InvalidTopology): PreviewGraph(n,self.edges)

    def test_duplicate_framework_rejected(self):
        n=copy.deepcopy(self.frameworks)
        n['objects'][1]['source_framework_id']=n['objects'][0]['source_framework_id']
        with self.assertRaises(InvalidTopology): PreviewGraph(n,self.edges)

    def test_unknown_framework_in_edge_rejected(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['target_id']='INJECTED-FRAMEWORK'
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_cross_station_road_requires_bridge(self):
        e=copy.deepcopy(self.edges)
        target=next(x for x in e['edges'] if x['edge_id']=='VIL-03')
        target['kind']='road'
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_unverified_bridge_cannot_mark_approved(self):
        e=copy.deepcopy(self.edges)
        target=next(x for x in e['edges'] if x['edge_id']=='VIL-03')
        target['bridge_approved']=True
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_wrong_station_binding_rejected(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['from_station']='VSR-KS-OTHER'
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_duplicate_directed_edge_id_rejected(self):
        e=copy.deepcopy(self.edges)
        e['edges'].append(copy.deepcopy(e['edges'][0]))
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_edge_authority_not_granted(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['authority_grant']=True
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_unknown_mode_denied(self):
        self.assertEqual(self.graph.preview('FOR-0001','FOR-0006',mode='lowest_price').disposition,'DENY')

    def test_invalid_weight_rejected(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['hop_weight']=0
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_bool_weight_rejected(self):
        e=copy.deepcopy(self.edges)
        e['edges'][0]['hop_weight']=True
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_untrusted_manifest_status_rejected(self):
        e=copy.deepcopy(self.edges)
        e['status']='PUBLISHED'
        with self.assertRaises(InvalidTopology): PreviewGraph(self.frameworks,e)

    def test_no_access_grant_for_metadata_preview(self):
        r=self.graph.preview('FOR-0001','FOR-0003')
        self.assertFalse(r.authority_granted)
        self.assertFalse(r.engine_execution_allowed)
        self.assertFalse(r.river_receipt_emitted)
        self.assertFalse(r.registered_in_genesis)
        self.assertFalse(r.deploy_allowed)

if __name__=='__main__':unittest.main()