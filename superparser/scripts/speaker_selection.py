"""Experimental speaker ranking: local native evidence, never source-specific rules.

All alternatives remain visible. These are ranking policies, not grammar,
and do not modify the production graph or equate independent MRS variables.
"""
from collections import defaultdict

OPAQUE={"fw_seq","unknown","quoted"}

def overlaps(a,b):
    return max(a[0],b[0])<min(a[1],b[1])

def evidence_rank(graph, attr, e):
    rd=next(r for r in graph["readings"] if r["id"]==e["reading_id"])
    tag=next(p for p in graph["source_nodes"] if p["id"]==attr["reporting_clause_id"])
    local=[p for p in rd["predications"] if any(overlaps(s,(tag["start"],tag["end"])) for s in p["source_spans"])]
    local_opaque=sum(p["predicate"].strip('"') in OPAQUE for p in local)
    # A native unknown or quoted predicate INSIDE the reporter is more
    # relevant to speaker reliability than a placeholder inside the quote.
    local_unknown=sum(p["predicate"].strip('"').endswith("_unknown") for p in local)
    # Prefer whole context, then native evidence with fewer local gaps.
    return (0 if rd["view_id"]=="whole" else 1,local_opaque,local_unknown,rd["native_rank"])

def speaker_options(graph, attr, policy):
    ev=[e for e in attr["native_report_evidence"] if e["speaker_source_spans"]]
    if not ev: return []
    if policy=="baseline":
        return [x["source_spans"] for x in attr["speaker_options"]]
    if policy=="native_rank":
        best=min((0 if e["reading_id"].startswith("whole/") else 1,
                  int(e["reading_id"].rsplit("rank",1)[1])) for e in ev)
        ev=[e for e in ev if (0 if e["reading_id"].startswith("whole/") else 1,
                  int(e["reading_id"].rsplit("rank",1)[1]))==best]
    elif policy in {"local_quality","local_quality_abstain"}:
        ranks=[(evidence_rank(graph,attr,e),e) for e in ev]
        # Quality-only retains ties rather than breaking them by arbitrary rank.
        cut=3 if policy=="local_quality_abstain" else 4
        best=min(s[:cut] for s,e in ranks)
        ev=[e for s,e in ranks if s[:cut]==best]
    else: raise ValueError("Unknown selector")
    return [[list(s) for s in k] for k in sorted({tuple(tuple(s) for s in e["speaker_source_spans"]) for e in ev})]

POLICIES=("baseline","native_rank","local_quality","local_quality_abstain")
