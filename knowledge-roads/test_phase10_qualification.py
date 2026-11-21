"""R0.10 reference qualification tests. Proposal coverage is not source approval."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from phase10_qualification import audit_qualification


ROOT = Path(__file__).resolve().parent


def load_file(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.proposals = load_file("registration_proposals.json")
        self.topology = load_file("phase9_proposed_edges.json")
        self.dossiers = load_file("phase10_qualification_dossiers.json")

    def result(self, proposal_edit=None, topology_edit=None, dossier_edit=None):
        p, t, d = deepcopy(self.proposals), deepcopy(self.topology), deepcopy(self.dossiers)
        if proposal_edit:
            proposal_edit(p)
        if topology_edit:
            topology_edit(t)
        if dossier_edit:
            dossier_edit(d)
        return audit_qualification(p, t, d)

    def assert_reason(self, reason, **edits):
        r = self.result(**edits)
        self.assertEqual(r.reason, reason)
        self.assertEqual(r.disposition, "DENY")
        self.assertFalse(r.genesis_registration_allowed)
        self.assertFalse(r.warden_navigation_allowed)
        self.assertFalse(r.engine_execution_allowed)
        self.assertFalse(r.river_receipt_emitted)
        self.assertFalse(r.publish_approved)

    def test_complete_dossier_is_only_hold(self):
        r = self.result()
        self.assertEqual(r.disposition, "HOLD")
        self.assertEqual(r.reason, "UNATTESTED_SOURCES_AND_UNQUALIFIED_TRANSITIONS")
        self.assertEqual(r.framework_count, 14)
        self.assertEqual(r.edge_count, 13)
        self.assertEqual(len(r.conceptual_bridges), 6)
        self.assertEqual(r.reviewed_qualified_count, 0)
        self.assertEqual(len(r.fingerprint), 64)
        self.assertFalse(r.genesis_registration_allowed)
        self.assertFalse(r.warden_navigation_allowed)
        self.assertFalse(r.engine_execution_allowed)
        self.assertFalse(r.river_receipt_emitted)

    def test_source_gaps_are_explicit(self):
        r = self.result()
        self.assertIn("FOR-0005", r.sources_without_references)
        self.assertIn("FOR-0006", r.sources_without_references)
        self.assertNotIn("FOR-0010", r.sources_without_references)

    def test_primary_research_keeps_original_credit(self):
        d = {x["framework_id"]: x for x in self.dossiers["objects"]}
        self.assertEqual(d["FOR-0010"]["author_credit"],
                         ["Albert Einstein", "Boris Podolsky", "Nathan Rosen"])
        self.assertEqual(d["FOR-0011"]["author_credit"],
                         ["Veronika E. Hubeny", "Mukund Rangamani", "Tadashi Takayanagi"])
        self.assertEqual(d["FOR-0012"]["author_credit"],
                         ["Ping Gao", "Daniel Louis Jafferis", "Aron C. Wall"])
        self.assertFalse(d["FOR-0012"]["execution_qualified"])

    def test_quantum_edges_explicitly_non_derivational(self):
        m = {e["edge_id"]: e for e in self.dossiers["edges"]}
        self.assertEqual(m["QNT-01"]["relationship_class"], "PEDAGOGICAL_SEQUENCE_NOT_DERIVATION")
        self.assertEqual(m["QNT-02"]["relationship_class"], "PEDAGOGICAL_SEQUENCE_NOT_DERIVATION")

    def test_no_proposal_state(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           proposal_edit=lambda p:p.update(status="ACTIVE"))

    def test_no_registry_count_claim(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           proposal_edit=lambda p:p.update(registration_count=14))

    def test_no_registration_action(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           proposal_edit=lambda p:p.update(registration_action_requested=True))

    def test_no_active_topology(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           topology_edit=lambda t:t.update(status="QUALIFIED"))

    def test_no_topology_authority(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           topology_edit=lambda t:t.update(authority_grants=1))

    def test_no_qualification_status_promotion(self):
        self.assert_reason("PROPOSAL_ONLY_STATE_REQUIRED",
                           dossier_edit=lambda d:d.update(status="APPROVED"))

    def test_wrong_proposal_bind(self):
        self.assert_reason("SOURCE_MANIFEST_BINDING_MISMATCH",
                           dossier_edit=lambda d:d.update(source_framework_manifest_id="OTHER"))

    def test_wrong_edge_bind(self):
        self.assert_reason("SOURCE_MANIFEST_BINDING_MISMATCH",
                           dossier_edit=lambda d:d.update(source_edges_manifest_id="OTHER"))

    def test_missing_framework_dossier(self):
        self.assert_reason("INCOMPLETE_DOSSIER_COVERAGE",
                           dossier_edit=lambda d:d["objects"].pop())

    def test_missing_edge_dossier(self):
        self.assert_reason("INCOMPLETE_DOSSIER_COVERAGE",
                           dossier_edit=lambda d:d["edges"].pop())

    def test_duplicate_framework_id(self):
        self.assert_reason("DUPLICATE_RECORD_ID",
                           dossier_edit=lambda d:d["objects"].append(deepcopy(d["objects"][0])))

    def test_duplicate_edge_id(self):
        self.assert_reason("DUPLICATE_RECORD_ID",
                           dossier_edit=lambda d:d["edges"].append(deepcopy(d["edges"][0])))

    def test_fake_counts(self):
        self.assert_reason("DOSSIER_COUNTS_MISMATCH",
                           dossier_edit=lambda d:d.update(object_count=15))

    def test_fake_authoritative_registration(self):
        self.assert_reason("PROPOSAL_REGISTRATION_OR_AUTHORITY_ESCALATION",
                           proposal_edit=lambda p:p["objects"][0].update(registration_state="ACTIVE"))

    def test_fake_engine_execution(self):
        self.assert_reason("PROPOSAL_REGISTRATION_OR_AUTHORITY_ESCALATION",
                           proposal_edit=lambda p:p["objects"][0].update(engine_execution_authorized=True))

    def test_fake_attribution_approval(self):
        self.assert_reason("FALSE_REVIEW_OR_AUTHORITY_CLAIM",
                           dossier_edit=lambda d:d["objects"][0].update(original_attribution_approved=True))

    def test_fake_rights_review(self):
        self.assert_reason("FALSE_REVIEW_OR_AUTHORITY_CLAIM",
                           dossier_edit=lambda d:d["objects"][0].update(rights_review="COMPLETED"))

    def test_fake_execution_qualification(self):
        self.assert_reason("FALSE_REVIEW_OR_AUTHORITY_CLAIM",
                           dossier_edit=lambda d:d["objects"][0].update(execution_qualified=True))

    def test_missing_original_author(self):
        self.assert_reason("PRIMARY_PUBLICATION_MISSING_AUTHORS",
                           dossier_edit=lambda d:next(x for x in d["objects"] if x["framework_id"]=="FOR-0010").update(author_credit=[]))

    def test_missing_applicability(self):
        self.assert_reason("MISSING_APPLICABILITY_OR_LIMITS",
                           dossier_edit=lambda d:d["objects"][0].update(applicability_conditions=[]))

    def test_missing_limits(self):
        self.assert_reason("MISSING_APPLICABILITY_OR_LIMITS",
                           dossier_edit=lambda d:d["objects"][0].update(non_applicability=[]))

    def test_unsafe_source_url(self):
        self.assert_reason("UNSAFE_SOURCE_REFERENCE",
                           dossier_edit=lambda d:d["objects"][0].update(source_urls=["http://unsafe.invalid"]))

    def test_userinfo_source_url(self):
        self.assert_reason("UNSAFE_SOURCE_REFERENCE",
                           dossier_edit=lambda d:d["objects"][0].update(source_urls=["https://user:pass@source.example.com/doc"]))

    def test_fake_source_review(self):
        self.assert_reason("UNSUPPORTED_SOURCE_REVIEW_CLAIM",
                           dossier_edit=lambda d:d["objects"][0].update(source_review_status="CERTIFIED"))

    def test_unapproved_engine_claim(self):
        self.assert_reason("UNREVIEWED_ENGINE_QUALIFICATION_CLAIM",
                           proposal_edit=lambda p:next(x for x in p["objects"] if x["source_framework_id"]=="FOR-0002").update(engine_qualification="PRODUCTION_APPROVED"))

    def test_fake_qualified_edge(self):
        self.assert_reason("FALSE_EDGE_QUALIFICATION_OR_AUTHORITY",
                           dossier_edit=lambda d:d["edges"][0].update(review_status="APPROVED"))

    def test_fake_scientific_derivation(self):
        self.assert_reason("FALSE_EDGE_QUALIFICATION_OR_AUTHORITY",
                           dossier_edit=lambda d:next(x for x in d["edges"] if x["edge_id"]=="QNT-01").update(scientific_derivation_claim=True))

    def test_fake_bridge_review(self):
        self.assert_reason("FALSE_EDGE_QUALIFICATION_OR_AUTHORITY",
                           dossier_edit=lambda d:d["edges"][0].update(bridge_approved=True))

    def test_missing_edge_conditions(self):
        self.assert_reason("EDGE_REVIEW_INCOMPLETE",
                           dossier_edit=lambda d:d["edges"][0].update(review_condition=""))

    def test_wrong_quantum_relationship(self):
        self.assert_reason("QUANTUM_RESEARCH_RELATIONSHIP_MISCLASSIFIED",
                           dossier_edit=lambda d:next(x for x in d["edges"] if x["edge_id"]=="QNT-02").update(relationship_class="PROVEN_CAUSAL_TRANSPORT"))

    def test_edge_source_authority(self):
        self.assert_reason("EDGE_ESCALATION_IN_SOURCE_TOPOLOGY",
                           topology_edit=lambda t:t["edges"][0].update(qualification_state="APPROVED"))

    def test_review_digest_bound_to_changed_source(self):
        original = self.result()
        other = self.result(dossier_edit=lambda d:d["objects"][0].update(attribution_note="New scholarly review required"))
        self.assertEqual(other.disposition, "HOLD")
        self.assertNotEqual(original.fingerprint, other.fingerprint)

    def test_review_digest_bound_to_edge_conditions(self):
        original = self.result()
        other = self.result(dossier_edit=lambda d:d["edges"][0].update(review_condition="Updated limitation"))
        self.assertNotEqual(original.fingerprint, other.fingerprint)

    def test_no_approval_when_source_urls_all_exist(self):
        def supply(d):
            for item in d["objects"]:
                if not item["source_urls"]:
                    item["source_urls"] = ["https://example.org/unverified"]
                    item["source_review_status"] = "CITATION_IDENTIFIED_UNAUDITED"
        self.assertEqual(self.result(dossier_edit=supply).disposition, "HOLD")


if __name__ == "__main__":
    unittest.main()
