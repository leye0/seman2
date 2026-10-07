#!/usr/bin/env python3
"""CULT-04: contextual transmission without essentialist culture attributes."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OUT = P / "output"
FORM = "My friend lost his leg in a car accident\nHe was hopping mad"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contextual_score(pattern: dict, query: dict) -> tuple[float, list[str], list[str]]:
    weights = {"community": 0.30, "period": 0.15, "register": 0.20, "relation": 0.25, "shared_history": 0.10}
    matched, mismatched, score = [], [], 0.0
    for field, weight in weights.items():
        if query[field] in pattern["contexts"][field]:
            score += weight
            matched.append(field)
        else:
            mismatched.append(field)
    return score, matched, mismatched


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c5 = ROOT / "poc/cult-05/output/results.json"
    posts_path = ROOT / "poc/cult-05/output/selected-posts-v2.parquet"
    comments_path = ROOT / "poc/cult-05/output/selected-comments-v2.parquet"
    c1 = ROOT / "poc/cult-01/output/results.json"
    assert all(p.exists() for p in (c5, posts_path, comments_path, c1))

    con = duckdb.connect()
    post_rows = con.execute(
        """SELECT submission_id,title,body,lower(subreddit) community,created_at,
                  native_vote_score,num_comments,source_file,source_position,source_record_id
           FROM read_parquet(?) WHERE submission_id IN ('8mi6ue','8mi71r') ORDER BY submission_id""",
        [str(posts_path)],
    ).fetchall()
    post_columns = [d[0] for d in con.description]
    real_posts = [dict(zip(post_columns, row)) for row in post_rows]
    reactions = {
        row[0]: {"observed_comments": row[1], "positive": row[2], "nonpositive": row[3]}
        for row in con.execute(
            """SELECT submission_id,count(*),sum((native_vote_score>0)::INT),sum((native_vote_score<=0)::INT)
               FROM read_parquet(?) WHERE submission_id IN ('8mi6ue','8mi71r') GROUP BY submission_id""",
            [str(comments_path)],
        ).fetchall()
    }
    duplicate_count = con.execute(
        """SELECT count(*),count(distinct lower(subreddit)) FROM read_parquet(?)
           WHERE lower(trim(title || '\n' || body))=lower(?)""",
        [str(posts_path), FORM],
    ).fetchone()
    con.close()
    assert duplicate_count == (2, 2), duplicate_count

    occurrences = []
    for post in real_posts:
        occurrences.append({
            "occurrence_id": f"TO-REAL-{post['submission_id']}",
            "surface": post["title"] + "\n" + post["body"],
            "period": "2018-05",
            "occurred_at": post["created_at"].isoformat(),
            "community": post["community"],
            "register": "public-forum-post",
            "relation": "author-to-unknown-audience",
            "shared_history": "unknown",
            "observed_outcome": "positive-public-reaction" if post["native_vote_score"] > 0 else "nonpositive-public-reaction",
            "outcome_evidence": {"native_vote_score": post["native_vote_score"], "declared_num_comments": post["num_comments"], **reactions.get(post["submission_id"], {})},
            "transmitted_from": None,
            "transmission_status": "independent-root; repost relation not proven",
            "provenance": {"kind": "real-corpus-record", "source_file": post["source_file"], "source_position": post["source_position"], "source_record_id": post["source_record_id"]},
        })

    fixtures = [
        ("TO-F01", "2024-Q1", "close-friends", "casual-spoken", "close-peers", "prior-wordplay", "affiliative-response", "TO-REAL-8mi71r"),
        ("TO-F02", "2024-Q1", "close-friends", "casual-spoken", "close-peers", "prior-wordplay", "offended-response", "TO-F01"),
        ("TO-F03", "2024-Q2", "mobility-support", "support-meeting", "newcomer-to-group", "none", "literal-concern", "TO-REAL-8mi6ue"),
        ("TO-F04", "2024-Q2", "mobility-support", "support-meeting", "established-peers", "known-dark-humour", "affiliative-response", "TO-F03"),
        ("TO-F05", "2025-Q3", "engineering-workplace", "formal-meeting", "employee-to-manager", "missed-deadline", "task-refocus", "TO-F01"),
        ("TO-F06", "2025-Q3", "engineering-workplace", "formal-meeting", "manager-to-employee", "mutual-joking", "affiliative-response", "TO-F05"),
        ("TO-F07", "2026-Q2", "jokes", "public-forum-post", "author-to-unknown-audience", "unknown", "nonpositive-public-reaction", "TO-REAL-8mi6ue"),
    ]
    for oid, period, community, register, relation, history, outcome, parent in fixtures:
        occurrences.append({
            "occurrence_id": oid, "surface": FORM, "period": period, "occurred_at": None,
            "community": community, "register": register, "relation": relation,
            "shared_history": history, "observed_outcome": outcome,
            "outcome_evidence": {"kind": "controlled expected-observation", "value": outcome},
            "transmitted_from": parent, "transmission_status": "controlled explicit reuse",
            "provenance": {"kind": "controlled-fixture", "fixture_id": oid, "claim_limit": "tests representation and retrieval, not empirical prevalence"},
        })

    patterns = [
        {
            "pattern_id": "CTX-P01", "anonymous": True,
            "contexts": {"community": ["jokes", "dadjokes", "close-friends"], "period": ["2018-05", "2024-Q1", "2026-Q2"], "register": ["public-forum-post", "casual-spoken"], "relation": ["author-to-unknown-audience", "close-peers"], "shared_history": ["unknown", "prior-wordplay"]},
            "expected_outcomes": ["positive-public-reaction", "affiliative-response"],
            "support_occurrences": ["TO-REAL-8mi6ue", "TO-REAL-8mi71r", "TO-F01"], "exception_occurrences": ["TO-F02", "TO-F07"],
            "human_gloss_eval_only": "public or familiar humorous use",
        },
        {
            "pattern_id": "CTX-P02", "anonymous": True,
            "contexts": {"community": ["mobility-support"], "period": ["2024-Q2"], "register": ["support-meeting"], "relation": ["newcomer-to-group", "established-peers"], "shared_history": ["none"]},
            "expected_outcomes": ["literal-concern"], "support_occurrences": ["TO-F03"], "exception_occurrences": ["TO-F04"],
            "human_gloss_eval_only": "literal-sensitive setting",
        },
        {
            "pattern_id": "CTX-P03", "anonymous": True,
            "contexts": {"community": ["engineering-workplace"], "period": ["2025-Q3"], "register": ["formal-meeting"], "relation": ["employee-to-manager", "manager-to-employee"], "shared_history": ["missed-deadline"]},
            "expected_outcomes": ["task-refocus"], "support_occurrences": ["TO-F05"], "exception_occurrences": ["TO-F06"],
            "human_gloss_eval_only": "formal task context",
        },
    ]
    by_id = {o["occurrence_id"]: o for o in occurrences}
    for pattern in patterns:
        assert all(oid in by_id for oid in pattern["support_occurrences"] + pattern["exception_occurrences"])
        pattern["support_count"] = len(pattern["support_occurrences"])
        pattern["exception_count"] = len(pattern["exception_occurrences"])
        pattern["outcome_distribution"] = dict(Counter(by_id[oid]["observed_outcome"] for oid in pattern["support_occurrences"] + pattern["exception_occurrences"]))

    queries = [
        {"query_id": "Q-PUBLIC", "community": "dadjokes", "period": "2018-05", "register": "public-forum-post", "relation": "author-to-unknown-audience", "shared_history": "unknown"},
        {"query_id": "Q-SUPPORT", "community": "mobility-support", "period": "2024-Q2", "register": "support-meeting", "relation": "newcomer-to-group", "shared_history": "none"},
        {"query_id": "Q-WORK", "community": "engineering-workplace", "period": "2025-Q3", "register": "formal-meeting", "relation": "employee-to-manager", "shared_history": "missed-deadline"},
        {"query_id": "Q-CROSSCUT", "community": "engineering-workplace", "period": "2025-Q3", "register": "casual-spoken", "relation": "close-peers", "shared_history": "prior-wordplay"},
    ]
    retrievals = []
    for query in queries:
        candidates = []
        for pattern in patterns:
            score, matched, mismatched = contextual_score(pattern, query)
            candidates.append({"pattern_id": pattern["pattern_id"], "contextual_score": score, "matched_dimensions": matched, "mismatched_dimensions": mismatched})
        candidates.sort(key=lambda row: (-row["contextual_score"], row["pattern_id"]))
        retrievals.append({"query": query, "ranking": candidates, "selected_pattern_id": candidates[0]["pattern_id"], "essentialist_prior_used": False})

    graph = nx.DiGraph()
    graph.add_nodes_from(by_id)
    edges = []
    for occurrence in occurrences:
        if occurrence["transmitted_from"]:
            edge = {"source": occurrence["transmitted_from"], "target": occurrence["occurrence_id"], "relation": "transmitted-as-controlled-reuse", "status": occurrence["transmission_status"]}
            graph.add_edge(edge["source"], edge["target"])
            edges.append(edge)
    occurrence_path, edge_path = OUT / "transmission-occurrences.parquet", OUT / "transmission-edges.parquet"
    pq.write_table(pa.Table.from_pylist([{**o, "outcome_evidence": json.dumps(o["outcome_evidence"]), "provenance": json.dumps(o["provenance"])} for o in occurrences]), occurrence_path, compression="zstd")
    pq.write_table(pa.Table.from_pylist(edges), edge_path, compression="zstd")

    selected = {r["query"]["query_id"]: r["selected_pattern_id"] for r in retrievals}
    serialized_schema = json.dumps({"occurrences": occurrences, "patterns": patterns, "retrievals": retrievals}, sort_keys=True).lower()
    validations = {
        "same_surface_all_occurrences": len({o["surface"].lower() for o in occurrences}) == 1,
        "real_exact_duplicate_crosses_communities": duplicate_count == (2, 2),
        "real_records_have_source_provenance": all(o["provenance"]["kind"] == "real-corpus-record" and o["provenance"]["source_file"] for o in occurrences[:2]),
        "fixtures_are_not_misrepresented_as_corpus": all(o["provenance"]["kind"] == "controlled-fixture" and "claim_limit" in o["provenance"] for o in occurrences[2:]),
        "multiple_periods_registers_relations_communities": all(len({o[field] for o in occurrences}) >= 3 for field in ("period", "register", "relation", "community")),
        "transmission_chain_is_acyclic_and_attributed": nx.is_directed_acyclic_graph(graph) and all(e["source"] in by_id and e["target"] in by_id for e in edges),
        "unproven_repost_link_not_asserted": all(o["transmitted_from"] is None and "not proven" in o["transmission_status"] for o in occurrences[:2]),
        "every_regularitity_has_exception": all(p["support_count"] and p["exception_count"] for p in patterns),
        "retrieval_changes_with_context": selected["Q-PUBLIC"] == "CTX-P01" and selected["Q-SUPPORT"] == "CTX-P02" and selected["Q-WORK"] == "CTX-P03",
        "crosscut_query_combines_dimensions": len(next(r for r in retrievals if r["query"]["query_id"] == "Q-CROSSCUT")["ranking"][0]["matched_dimensions"]) >= 2,
        "no_global_culture_or_member_score": "culture_score" not in serialized_schema and "member_score" not in serialized_schema and all(not r["essentialist_prior_used"] for r in retrievals),
        "no_culture_implies_intention_rule": "culture=" not in serialized_schema and "intention=" not in serialized_schema,
        "outcomes_remain_distributions": all(len(p["outcome_distribution"]) >= 2 for p in patterns),
        "parquet_roundtrip": pq.read_table(occurrence_path).num_rows == len(occurrences) and pq.read_table(edge_path).num_rows == len(edges),
    }
    assert all(validations.values()), validations
    result = {
        "invariant_form": FORM,
        "real_corpus_discovery": {"exact_occurrences": 2, "distinct_communities": 2, "submission_ids": [p["submission_id"] for p in real_posts]},
        "transmission_occurrences": occurrences, "transmission_edges": edges,
        "anonymous_context_patterns": patterns, "contextual_retrievals": retrievals,
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in (c5, posts_path, comments_path, c1)},
        "limitations": [
            "Only the two marked Reddit occurrences are empirical corpus records.",
            "Controlled observations test contextual representation and exceptions; they do not establish population prevalence.",
            "An edge denotes known controlled reuse only; identical real posts are not assumed to share a transmission chain.",
        ],
        "artifacts": {"occurrences": {"path": "output/transmission-occurrences.parquet", "sha256": sha(occurrence_path)}, "edges": {"path": "output/transmission-edges.parquet", "sha256": sha(edge_path)}},
        "validations": validations,
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    (OUT / "summary.json").write_text(json.dumps({
        "occurrences": len(occurrences), "real_corpus_occurrences": 2, "controlled_occurrences": len(fixtures),
        "transmission_edges": len(edges), "context_patterns": len(patterns), "patterns_with_exceptions": len(patterns),
        "verdict": "GO_CONTEXTUAL_TRANSMISSION_WITHOUT_ESSENTIALISM",
    }, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "duckdb": importlib.metadata.version("duckdb"), "networkx": importlib.metadata.version("networkx"),
        "pyarrow": importlib.metadata.version("pyarrow"), "retrieval_weights": {"community": .30, "period": .15, "register": .20, "relation": .25, "shared_history": .10},
    }, indent=2) + "\n")
    print("CULT-04: real cross-community duplicate + attributed transmission/context exceptions; GO")


if __name__ == "__main__":
    main()
