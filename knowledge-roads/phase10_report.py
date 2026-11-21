"""Render a local review-only report. Does not register, qualify or grant anything."""
import json
from pathlib import Path
from phase10_review_gate import evaluate,reviewer_packet

ROOT=Path(__file__).parent
load=lambda name:json.loads((ROOT/name).read_text())


def report():
    result=evaluate(load('registration_proposals.json'),load('phase9_proposed_edges.json'),
                    load('phase10_qualification_dossiers.json'))
    return {
        'status':result.disposition,
        'reason':result.reason,
        'counts':{'frameworks':result.framework_count,'edges':result.edge_count,
                  'references_identified_not_audited':result.citation_identified,
                  'references_or_provenance_missing':result.citation_missing,
                  'qualified_objects':0,'qualified_edges':0,'live_registrations':0},
        'review_packet':reviewer_packet(result),
        'blockers':list(result.review_blockers),
        'real_authority_granted':False,
        'engine_execution_allowed':False,
        'river_receipt_emitted':False,
    }

if __name__=='__main__':print(json.dumps(report(),indent=2))