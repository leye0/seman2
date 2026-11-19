"""Mine bounded composition candidates from the pinned Novel-1000 v3 replay.

This is an observer, not a gold annotator or a second parser. An observed
rule, feature, anchor or graph edge is evidence about the current winner,
not evidence that the winner is grammatical.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import novel_ladder as ladder
from scripts import novel_source_reporting_v3 as v3

ENDS = (500, 600, 700, 800, 900, 1000)
TRANSFER_BOOK = 120  # Treasure Island, retrospective cross-book check
FINITE_PAIR = frozenset({
    "vp_coord_finite", "vp_finite_comma_coord_shared_subject",
})


def walk(node):
    yield node
    for child in node["children"]:
        yield from walk(child)


def anchor(node, name):
    value = node["syntax"]["anchors"].get(name, "")
    fields = value.split(":", 4)
    if len(fields) != 5 or fields[0] != "lex":
        return None
    start, end = (int(field) for field in fields[1:3])
    if not node["span"][0] <= start < end <= node["span"][1]:
        return None
    return {"span": [start, end], "category": fields[3], "lemma": fields[4]}


def graph_edges(row):
    graph = row["selected_graph"]["graph"]
    spans = {n["id"]: n["span"] for n in graph["nodes"]}
    return [(e["relation"], spans[e["source"]], spans[e["target"]])
            for e in graph["relations"]]


def roles(edges, owner, argument):
    return sorted({r for r, s, t in edges
                   if s == owner["span"] and t == argument["span"]})


def relative(node, edges):
    head, clause = node["children"]
    antecedent = anchor(head, "referent")
    marker = None
    if node["rule_id"] == "np_relative_subj":
        if clause["rule_id"] not in {"wh_subj_clause", "wh_supplementary_subject_comma"}:
            return None
        tag, producer = "subject", clause
        owner = anchor(clause, "predicate") or anchor(clause, "event")
        marker = anchor(clause, "subject")
    else:
        if clause["rule_id"] not in {"wh_bare", "wh_obj_clause",
                                     "wh_bare_perfect_object_relative"}:
            return None
        producer = clause["children"][-1]
        tag = producer["features"].get("gap")
        if tag not in {"object", "pp"}:
            return None
        owner = (anchor(producer, "prep") if tag == "pp" else
                 (anchor(producer, "lexical_predicate") or anchor(producer, "event")))
    if antecedent is None or owner is None:
        return None
    return {"family": "headed_relative_slot_binding", "variant": tag,
            "route": [node["rule_id"], clause["rule_id"], producer["rule_id"]],
            "span": node["span"], "antecedent": antecedent, "owner": owner,
            "direct_graph_roles": roles(edges, owner, antecedent),
            "relative_subject_graph_roles": roles(edges, owner, marker) if marker else []}


def finite_pair(node, edges):
    if len(node["children"]) != 2:
        return None
    nominal, pair = node["children"]
    subject = anchor(node, "subject")
    if (nominal["category"] != "NP" or pair["category"] != "VP"
            or pair["features"].get("vform") != "finite"
            or subject is None or anchor(nominal, "referent") != subject):
        return None
    if pair["rule_id"] in FINITE_PAIR:
        variant, names = "canonical_vp_pair", ("left", "right")
    elif pair["features"].get("source_shared_finite") == "true":
        variant, names = "scoped_vp_pair", ("first_predicate", "second_predicate")
    else:
        return None
    first, second = (anchor(pair, name) for name in names)
    if first is None or second is None or first["span"][1] > second["span"][0]:
        return None
    return {"family": "shared_finite_subject_binding", "variant": variant,
            "route": [node["rule_id"], pair["rule_id"]], "span": node["span"],
            "subject": subject, "first": first, "second": second,
            "first_graph_roles": roles(edges, first, subject),
            "second_graph_roles": roles(edges, second, subject),
            "coordination_graph_roles": roles(edges, first, second)}


def object_control(node, edges):
    event, obj, complement = (anchor(node, name) for name in ("event", "object", "inf"))
    if event is None or obj is None or complement is None:
        return None
    return {"family": "embedded_subject_selection", "variant": node["rule_id"],
            "route": [node["rule_id"]], "span": node["span"], "governor": event,
            "object": obj, "embedded_predicate": complement,
            "embedded_graph_roles": roles(edges, complement, obj)}


def edges_between(edges, left, right):
    def inside(span, part):
        return span and part["start"] <= span[0] < span[1] <= part["end"]

    return [{"relation": r, "source_span": s, "target_span": t}
            for r, s, t in edges if inside(s, left) and inside(t, right)]


def split_turns(constituents, edges):
    """Require the source's declared shared reporter and resumption, not quotes alone."""
    turns = [c for c in constituents if c["function"] == "split_direct_speech_turn"]
    for turn in turns:
        reports = [c for c in constituents if c["function"] == "reporting_clause"
                   and c["governor"] == turn["id"] and c["relation"] == "intercalated_speech_tag"]
        if len(reports) != 1:
            continue
        report, = reports
        quotes = [c for c in constituents if c["function"] == "direct_speech"]
        firsts = [c for c in quotes if c["governor"] == report["id"]
                  and c["relation"] == "reported_content"]
        if len(firsts) != 1:
            continue
        first, = firsts
        seconds = [c for c in quotes if c["governor"] == first["id"]
                   and c["relation"] == "resumption_of_split_speech"]
        if len(seconds) != 1:
            continue
        second, = seconds
        if not (turn["start"] == first["start"] and turn["end"] == second["end"]
                and first["end"] <= report["start"] < report["end"] <= second["start"]):
            continue
        yield {"family": "split_speech_attribution", "variant": turn["evidence"],
               "span": [turn["start"], turn["end"]],
               "source_constituents": {key: [c["start"], c["end"]] for key, c in
                                       (("first", first), ("report", report), ("second", second))},
               "report_to_first": edges_between(edges, report, first),
               "report_to_second": edges_between(edges, report, second),
               "first_to_second": edges_between(edges, first, second)}


def observe(row):
    edges = graph_edges(row)
    base = {key: row[key] for key in
            ("transfer_id", "book_id", "structural_core_source_span", "source_text", "root_rule")}
    for node in walk(row["tree"]):
        if node["rule_id"] in {"np_relative_subj", "np_relative_obj"}:
            candidate = relative(node, edges)
        elif node["rule_id"] in {"vp_obj_control", "vp_obj_control_bare"}:
            candidate = object_control(node, edges)
        else:
            candidate = finite_pair(node, edges)
        if candidate is not None:
            yield {**base, **candidate}
    for candidate in split_turns(row["structural_constituents"], edges):
        yield {**base, **candidate}


def replay_rows(directory):
    manifest, groups, _ = v3.prepare()
    pin = ladder.read_json(v3.DIRECTORY / "baseline.json")
    source_pin = ladder.read_json(v3.DIRECTORY / "source-manifest.json")
    if manifest != source_pin or ladder.digest(manifest) != pin["manifest_sha256"]:
        raise ValueError("Novel-1000 v3 source manifest changed")
    for end in ENDS:
        header, cases = groups[str(end)]
        result = ladder.read_json(directory / f"novel-{end}-result.json")
        with (directory / f"novel-{end}-parses.jsonl").open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
        if (result["cohort_sha256"] != header["cohort_sha256"]
                or result["limits"] != ladder.LIMITS or len(rows) != len(cases)
                or any(any(row.get(key) != val for key, val in case.items())
                       for row, case in zip(rows, cases))
                or ladder.digest(ladder.signatures(rows))
                != pin["cohorts"][str(end)]["ordered_signatures_sha256"]):
            raise ValueError(f"Unexpected source, budgets or selected outputs for Novel-{end}")
        yield from rows


def graph_signals(row):
    for name in ("direct_graph_roles", "relative_subject_graph_roles",
                 "first_graph_roles", "second_graph_roles", "embedded_graph_roles"):
        if row.get(name):
            yield name
    if "CONJUNCT" in row.get("coordination_graph_roles", ()):
        yield "conjunct_between_predicates"
    if (any(e["relation"] == "REPORTED_CONTENT" for e in row.get("report_to_first", ()))
            and any(e["relation"] == "CONTINUED_SPEECH" for e in row.get("first_to_second", ()))):
        yield "report_to_first_and_continuation"


def summarize(candidates):
    variants = sorted({(c["family"], c["variant"]) for c in candidates})
    result = []
    for family, variant in variants:
        rows = [c for c in candidates if (c["family"], c["variant"]) == (family, variant)]
        books = Counter(c["book_id"] for c in rows)
        result.append({"family": family, "variant": variant, "hits": len(rows),
                       "passages": len({c["transfer_id"] for c in rows}),
                       "by_book": dict(sorted(books.items())),
                       "discovery_hits": len(rows) - books[TRANSFER_BOOK],
                       "cross_book_hits": books[TRANSFER_BOOK],
                       "graph_signals": dict(sorted(Counter(
                           signal for row in rows for signal in graph_signals(row)
                       ).items()))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    corpus = Counter()
    candidates = []
    for row in replay_rows(args.replay_dir):
        corpus[row["book_id"]] += 1
        candidates.extend(observe(row))
    report = {"schema": "seman2-novel1000-pattern-audit-v1",
              "sources": dict(sorted(corpus.items())), "cross_book": TRANSFER_BOOK,
              "summary": summarize(candidates)}
    if not args.summary_only:
        report["candidates"] = candidates
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
