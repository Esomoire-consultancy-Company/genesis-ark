"""Run four no-network, non-authorizing VSR Knowledge Roads examples."""
from __future__ import annotations
import json
from pathlib import Path
from phase9_route_compiler import PreviewGraph, safe_public_summary

HERE=Path(__file__).resolve().parent

def main() -> None:
    manifest=json.loads((HERE/'registration_proposals.json').read_text())
    edges=json.loads((HERE/'phase9_proposed_edges.json').read_text())
    graph=PreviewGraph(manifest,edges)
    scenarios={
        'village_development':('FOR-0001','FOR-0006','fewer-bridges'),
        'buffet_replenishment':('FOR-0008','FOR-0006','fewer-bridges'),
        'quantum_research':('FOR-0010','FOR-0012','fewest-hops'),
        'distributed_systems':('FOR-0013','FOR-0006','fewer-bridges'),
    }
    out={'classification':'PUBLIC_PROPOSED_REFERENCE_DEMONSTRATION',
         'physical_route':False,'real_admission':False,'engine_execution_enabled':False,
         'scenarios':{name:safe_public_summary(graph.preview(s,d,mode=m))
                      for name,(s,d,m) in scenarios.items()}}
    print(json.dumps(out,indent=2))

if __name__=='__main__': main()