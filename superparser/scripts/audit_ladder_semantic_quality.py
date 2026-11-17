"""Audit selected syntax and semantic graphs, not just parser completion.

This audit inventories EVERY case of frozen Novel-700 and exploratory
Novel-800. Automatic checks are necessary but are NEVER sufficient to mark
a case as linguistically verified. Reviews require independently written
source-grounded evidence and tests; neither a digest nor a green replay
provides evidence of correctness.

Usage:
  PYTHONPATH=superparser python -m scripts.audit_ladder_semantic_quality \
    --novel700 /tmp/novel-700-parses.jsonl \
    --novel800 /tmp/novel-800-candidate-parses.jsonl \
    --out /tmp/semantic-audit --gate
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from scripts import novel_ladder as ladder
from scripts.evaluate_novel_transfer import ROOT

CURRENT700 = ROOT / "research" / "novel_ladder" / "novel-700-current.json"
REVIEW700 = ROOT / "research" / "novel_ladder" / "novel-700-review.json"
COHORT700 = ROOT / "research" / "novel_ladder" / "novel-700-cohort.json"
CURRENT800 = ROOT / "research" / "novel_800_exploration" / "novel-800-candidate-current.json"
REVIEW800 = ROOT / "research" / "novel_800_exploration" / "novel-800-candidate-review.json"
COHORT800 = ROOT / "research" / "novel_800_exploration" / "novel-800-candidate-cohort.json"
DEFECTS = ROOT / "research" / "semantic_quality" / "confirmed_selected_defects.json"

NEGATORS = frozenset(("not", "never", "n't", "n’t"))
MODALS = frozenset(("can", "could", "may", "might", "must", "shall", "should", "will", "would"))
REPORTERS = frozenset(("say", "reply", "ask", "answer", "cry", "exclaim", "return", "complain"))
TERMINALS = frozenset((".", "?", "!", "”", "’", '"', "'", "…"))

def load_lines(path: Path) -> list[dict[str, Any]]:
    result = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(result) != 100:
        raise AssertionError(f"{path}: expected exactly 100 rows, found {len(result)}")
    return result

def _leaves(tree: dict[str, Any]) -> list[dict[str, Any]]:
    children = tree.get("children", ())
    if not children:
        return [tree]
    return [leaf for c in children for leaf in _leaves(c)]

def fingerprint_and_source(row, expected, anchor) -> None:
    index=row["ladder_index"]
    if (row["status"]!="complete" or row["root_rule"]!=expected["root_rule"]
        or ladder.digest(row.get("tree"))!=expected["rank_one_sha256"]
        or ladder.graph_digest(row.get("selected_graph"))!=expected["selected_graph_sha256"]
        or row["book_id"]!=anchor[1]
        or row["structural_paragraph_index"]!=anchor[2]
        or list(row["structural_core_source_span"])!=anchor[3:5]
        or row["band"]!=anchor[5]
        or ladder.case_hash(row)!=anchor[6]
        or row["forest_budget_exceeded"]!=expected["forest_budget_exceeded"]
        or row["kbest_budget_exceeded"]!=expected["kbest_budget_exceeded"]):
        raise AssertionError(f"N{index}: rank-one tree/graph/source/budget drift")

def inspect(row: dict[str, Any], old_review: dict[str, Any] | None,
            known_defect: dict[str, Any] | None = None) -> dict[str, Any]:
    index=row["ladder_index"]
    text=row["source_text"]
    tree=row["tree"]
    package=row["selected_graph"]
    graph=package["graph"]
    nodes={n["id"]:n for n in graph["nodes"]}
    edges=graph["relations"]
    issues=[]
    informational=[]
    if len(nodes)!=len(graph["nodes"]):
        issues.append("DUPLICATE_SEMANTIC_NODE_ID")
    for edge in edges:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            issues.append("DANGLING_GRAPH_RELATION")
    if tree["span"][0]!=0 or tree["span"][1]>len(text):
        issues.append("INVALID_SELECTED_TREE_SPAN")
    elif tree["span"][1]!=len(text):
        suffix=text[tree["span"][1]:]
        if suffix and all(ch in TERMINALS for ch in suffix):
            informational.append("ROOT_EXCLUDES_TERMINAL_PUNCTUATION")
        else:
            issues.append("ROOT_OMITS_SOURCE_CONTENT")
    for leaf in _leaves(tree):
        a,b=leaf["span"]
        if a<0 or b>len(text) or a>=b:
            issues.append("INVALID_LEAF_SPAN")
    for node in graph["nodes"]:
        span=node.get("span")
        surface=node.get("surface")
        if span is None:
            continue
        if len(span)!=2 or span[0]<0 or span[1]>len(text) or span[0]>=span[1]:
            issues.append("INVALID_GRAPH_NODE_SPAN")
        elif surface is None:
            informational.append("ABSTRACT_SEMANTIC_NODE_WITH_SOURCE_SPAN")
        elif text[span[0]:span[1]]!=surface:
            issues.append("SEMANTIC_NODE_SURFACE_DISAGREES_WITH_SOURCE")
    if not edges and any(n.get("kind")=="event" for n in graph["nodes"]):
        issues.append("EVENT_GRAPH_WITH_NO_RELATIONS")
    for node in graph["nodes"]:
        surface=(node.get("surface") or "").casefold()
        relation_count=sum(
            e["source"]==node["id"] or e["target"]==node["id"] for e in edges
        )
        if surface in NEGATORS and relation_count==0:
            issues.append("UNSCOPED_NEGATION")
        if surface in MODALS and node.get("type")=="MODAL" and relation_count==0:
            issues.append("UNSCOPED_MODAL")
        if surface=="oh" and node.get("type") in ("PERSON", "LOCATION"):
            issues.append("INTERJECTION_MISCLASSIFIED_AS_ENTITY")
        if surface=="dear" and node.get("type")=="PERSON":
            informational.append("DEAR_POSSIBLY_MISCLASSIFIED_AS_PERSON")
        if surface=="won" and "won't" in text.lower() and node.get("attributes",{}).get("lemma")=="win":
            issues.append("WONT_MISREAD_AS_WIN_VERB")
        if surface=="cap" and "cap'n" in text.lower() and node.get("kind")=="event":
            issues.append("DIALECTAL_VOCATIVE_MISREAD_AS_VERB")
    for node in graph["nodes"]:
        if node.get("kind")=="event" and not any(
            e["source"]==node["id"] or e["target"]==node["id"] for e in edges
        ):
            informational.append("UNATTACHED_EVENT")
    issues=list(dict.fromkeys(issues))
    informational=list(dict.fromkeys(informational))
    # These are objective interface defects or obvious lexical/role risk signals;
    # they do NOT attempt to infer all correct linguistic attachments.
    semantic_edges=[
        {"relation":e["relation"],
         "source": (nodes[e["source"]].get("surface") if e["source"] in nodes else None),
         "target": (nodes[e["target"]].get("surface") if e["target"] in nodes else None)}
        for e in edges
    ]
    lexical_leaves=[
        {"surface":text[leaf["span"][0]:leaf["span"][1]],"cat":leaf["category"],
         "lemma":(leaf.get("provenance",{}).get("detail",{}) or {}).get("lemma")}
        for leaf in _leaves(tree)
        if len(leaf.get("span",()))==2 and
        0<=leaf["span"][0]<=leaf["span"][1]<=len(text)
    ]
    existing_review=old_review["verdict"] if old_review else "unreviewed"
    signature_match=(known_defect is not None
        and known_defect["selected_tree_sha256"]==ladder.digest(tree)
        and known_defect["selected_graph_sha256"]==ladder.graph_digest(package))
    if known_defect is not None:
        quality_state=("needs_fix" if signature_match
                       else "changed_since_defect_requires_independent_recheck")
    elif existing_review=="verified" and issues:
        quality_state="review_conflict"
    else:
        quality_state=existing_review
    return {
        "index":index,
        "quality_state":quality_state,
        "confirmed_defect":({
            "observed":known_defect["observed_defect"],
            "required":known_defect["required_linguistic_correction"],
            "bad_signature_unchanged":signature_match,
        } if known_defect else None),
        "book_id":row["book_id"],
        "source":text,
        "source_span":row["structural_core_source_span"],
        "selected_rule":row["root_rule"],
        "selected_tree_sha256":ladder.digest(tree),
        "selected_graph_sha256":ladder.graph_digest(package),
        "review_status":old_review["verdict"] if old_review else "unreviewed",
        "review_evidence":old_review["evidence"] if old_review else None,
        "automatic_issues":issues,
        "automatic_warnings":informational,
        "leaves":lexical_leaves,
        "semantic_relations":semantic_edges,
    }

def audit_collection(path, *, first, expected_path, cohort_path, review_path, known_defects):
    expected=ladder.read_json(expected_path)
    cohort=ladder.read_json(cohort_path)
    reviews=ladder.read_json(review_path)
    old={e["index"]:e for e in reviews["cases"]}
    if (reviews["cohort_sha256"]!=cohort["cohort_sha256"]
        or expected["cohort_sha256"]!=cohort["cohort_sha256"]):
        raise AssertionError("Cohort/review source identity changed")
    rows=load_lines(path)
    by_result=ladder.result_cases(expected,cohort,first+99)
    observed=[]
    for offset,row in enumerate(rows):
        index=first+offset
        if row["ladder_index"]!=index:
            raise AssertionError(f"Unexpected cohort position N{row['ladder_index']}")
        fingerprint_and_source(row,by_result[index],cohort["anchors"][offset])
        entry=old.get(index)
        if entry is not None:
            if (entry["rank_one_sha256"]!=by_result[index]["rank_one_sha256"] or
                entry["selected_graph_sha256"]!=by_result[index]["selected_graph_sha256"]):
                raise AssertionError(f"Stale individual review N{index}")
        observed.append(inspect(row,entry,known_defects.get(index)))
    return observed

def run(args):
    ledger=ladder.read_json(DEFECTS)
    if ledger.get("schema")!="seman2-selected-semantic-defect-ledger-v1":
        raise AssertionError("Unknown semantic defect ledger schema")
    known_defects={r["index"]:r for r in ledger["cases"]}
    if len(known_defects)!=len(ledger["cases"]):
        raise AssertionError("Duplicate semantic defect IDs")
    if any(r["status"]!="needs_fix" for r in known_defects.values()):
        raise AssertionError("Cannot silently drop a known semantic defect")
    entries=[
        *audit_collection(args.novel700,first=601,expected_path=CURRENT700,
                          cohort_path=COHORT700,review_path=REVIEW700,known_defects=known_defects),
        *audit_collection(args.novel800,first=701,expected_path=CURRENT800,
                          cohort_path=COHORT800,review_path=REVIEW800,known_defects=known_defects)
    ]
    if len(entries)!=200 or len({e["index"] for e in entries})!=200:
        raise AssertionError("Expected 200 unique source-anchored reviewed candidates")
    flags=Counter(issue for entry in entries for issue in entry["automatic_issues"])
    warnings=Counter(issue for entry in entries for issue in entry["automatic_warnings"])
    counts=Counter(entry["quality_state"] for entry in entries)
    synopsis={
        "cohorts":{"Novel-700":CURRENT700.name,"Novel-800":CURRENT800.name},
        "total_cases":200,"complete_selected_trees":200,
        "individual_reviewed":counts["verified"],
        "individual_needs_fix":counts["needs_fix"],
        "individual_review_conflicts":counts["review_conflict"],
        "individual_recheck_needed":counts["changed_since_defect_requires_independent_recheck"],
        "individual_unreviewed":counts["unreviewed"],
        "original_review_coverage":sum(e["review_status"]=="verified" for e in entries),
        "individual_review_coverage":f"{counts['verified']}/200",
        "confirmed_semantic_defects":len(known_defects),
        "automatic_issue_cases":sum(bool(e["automatic_issues"]) for e in entries),
        "automatic_issue_types":dict(flags),
        "automatic_warning_types":dict(warnings),
        "audit_is_necessary_not_sufficient":True,
    }
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"semantic-audit-all-200.json").write_text(
        json.dumps({"summary":synopsis,"cases":entries},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8"
    )
    ranked=sorted((e for e in entries if e["automatic_issues"]
                   or e["confirmed_defect"]),
                  key=lambda e:(e["quality_state"] not in ("needs_fix","review_conflict"),
                                -len(e["automatic_issues"]),e["index"]))
    lines=[
        "# Semantic fidelity: **not certified**",
        "",
        "Automated inspection of exact source, selected syntax tree, graph nodes,",
        "graph edges and saved review digests across all 200 cases.",
        "These checks do **not** convert unreviewed trees to verified; every",
        "linguistic attachment still needs source-grounded human/model review,",
        "independent positive/negative controls, and explicit verdicts.",
        "",
        f"- **{synopsis['individual_reviewed']}** verified without an automatic contradiction",
        f"- **{synopsis['individual_needs_fix']}** individually identified wrong selected trees",
        f"- **{synopsis['individual_review_conflicts']}** previously verified analyses needing recheck",
        f"- **{synopsis['individual_unreviewed']}** still lacking individual review",
        f"- **{synopsis['automatic_issue_cases']}** cases with automatic issue flags",
        "",
        "## Prioritized issues",
        "",
        "| Case | Quality verdict | Source | Confirmed selected defect / automatic issues |",
        "| --- | --- | --- | --- |",
    ]
    for e in ranked:
        source=e["source"].replace("|","\\|").replace("\n"," ")[:100]
        known=e["confirmed_defect"]
        reason=known["observed"] if known else ""
        reason=reason.replace("|","/")[:150]
        flags=", ".join(e["automatic_issues"])
        lines.append(f"| N{e['index']} | {e['quality_state']} | {source} | "
                     f"{reason} {flags} |")
    lines.extend(["", "## Guardrail", "",
                  "Full coverage and digest stability are not semantic accuracy.",
                  "The final acceptance gate must remain closed until every case",
                  "has an individually verified selected tree and semantic graph,",
                  "and all known semantic issues are resolved.", ""])
    (args.out/"semantic-audit-report.md").write_text("\n".join(lines),encoding="utf-8")
    print("SEMANTIC_AUDIT_SUMMARY",json.dumps(synopsis,sort_keys=True),flush=True)
    for e in ranked:
        print("SEMANTIC_AUDIT_FLAG",json.dumps({
            "index":e["index"],"source":e["source"][:155],
            "status":e["quality_state"],"issues":e["automatic_issues"],"confirmed":bool(e["confirmed_defect"])
        },ensure_ascii=False),flush=True)
    if args.gate and (counts["unreviewed"] or counts["needs_fix"] or counts["review_conflict"] or counts["changed_since_defect_requires_independent_recheck"] or ranked):
        raise SystemExit(
            "Semantic acceptance blocked: unreviewed analyses and/or flagged defects remain"
        )

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--novel700",type=Path,required=True)
    parser.add_argument("--novel800",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--gate",action="store_true")
    run(parser.parse_args())

if __name__=="__main__":
    main()
