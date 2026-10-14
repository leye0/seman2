#!/usr/bin/env python3
"""Auditable multi-axis evaluation of the 300-sentence reference corpus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from seman_parser import Parser  # noqa: E402


LEXICAL_EQUIVALENTS = {
    "ADP": {"PREP", "PREP-BY"},
    "AUX": {"AUX", "AUX-BE", "COPULA", "HAVE"},
    "CCONJ": {"COORD"},
    "DET": {"DET"},
    "N": {"N"},
    "PROPN": {"PROPER-NOUN"},
    "PRON": {"PRONOUN", "EXPL"},
    "REL": {"WH-PRONOUN", "COMP-THAT"},
    "SCONJ": {"COMP-THAT", "CONJ"},
    # UD calls the English genitive clitic PART; Superparser's POSS retains
    # its grammatical function.  This is notation, not a lexical error.
    "PART": {"NEG", "TO", "PARTICLE", "POSS"},
    "V": {"V"},
    "ADJ": {"ADJ"},
    "ADV": {"ADV", "WH-NOM"},
    "MODAL": {"MODAL"},
    "PUNCT": {"COMMA"},
}

LEAF_ALIASES = {
    parser_category: gold_category
    for gold_category, parser_categories in LEXICAL_EQUIVALENTS.items()
    for parser_category in parser_categories
}

RULE_CATEGORY = {
    "np_gerund": "NP-GERUND",
    "np_coord": "NP-COORD",
    "np_gerund_coord": "NP-COORD",
    "np_wh_list": "NP-LIST",
    "np_colon_list": "NP-LIST",
    "vp_coord": "VP-COORD",
    "vp_coord_finite": "VP-COORD",
    "vp_list3": "VP-LIST",
    "wh_subj_clause": "RELCLAUSE",
    "wh_obj_clause": "RELCLAUSE",
    "wh_bare": "RELCLAUSE",
}

SKIP_GOLD_UNARY = {"ADJP", "ADVP"}
SKIP_PARSER_UNARY = {"ADJP", "ADVP"}


def walk_parser(item: Any) -> Iterable[Any]:
    yield item
    for child in item.children:
        yield from walk_parser(child)


def raw_gold(node: dict[str, Any]) -> Counter[tuple[str, int, int]]:
    out = Counter({(node["category"], *node["span"]): 1})
    for child in node.get("children", ()):
        out.update(raw_gold(child))
    return out


def raw_parser(item: Any | None) -> Counter[tuple[str, int, int]]:
    if item is None:
        return Counter()
    return Counter((node.category, node.start, node.end) for node in walk_parser(item))


def normalized_gold(
    node: dict[str, Any], parent: dict[str, Any] | None = None,
) -> Counter[tuple[str, int, int]]:
    children = node.get("children", ())
    category = node["category"]
    skip = (
        category == "SBAR"
        or (
            category in SKIP_GOLD_UNARY and len(children) == 1
            and children[0]["span"] == node["span"]
        )
        or (
            category == "CLAUSE" and node.get("role") == "content"
            and parent is not None and parent["category"] == "RELCLAUSE"
        )
        or (
            category == "VP"
            and [child["category"] for child in children] == ["AUX", "PART", "V"]
        )
    )
    out: Counter[tuple[str, int, int]] = Counter()
    if not skip:
        out[(category, *node["span"])] += 1
    for child in children:
        out.update(normalized_gold(child, node))
    return out


def _parser_category(item: Any, ancestors: tuple[Any, ...]) -> str:
    if item.rule_id in RULE_CATEGORY:
        return RULE_CATEGORY[item.rule_id]
    if item.category == "VP-GAP" or item.category == "VP-NP":
        return "VP"
    if item.lexical_candidate is not None:
        category = item.category
        if category == "COMP-THAT" and any(
            ancestor.rule_id in {"wh_obj_clause", "wh_subj_clause"}
            for ancestor in ancestors
        ):
            return "REL"
        return LEAF_ALIASES.get(category, category)
    return item.category


def normalized_parser(
    item: Any | None, parent: Any | None = None, ancestors: tuple[Any, ...] = (),
) -> Counter[tuple[str, int, int]]:
    if item is None:
        return Counter()
    category = _parser_category(item, ancestors)
    normalized_start = item.start
    if item.category == "VP-NP" and parent is not None and parent.rule_id in {
        "vp_to_inf", "vp_obj_control",
    }:
        # SuperParser preserves TO as the control verb's child while the
        # reference wraps TO + the bare predicate in VP-INF.
        category = "VP-INF"
        normalized_start = next(
            child.start for child in parent.children
            if child.category == "TO" and child.end <= item.start
        )
    skip = False
    if category in SKIP_PARSER_UNARY and len(item.children) == 1:
        child = item.children[0]
        skip = child.start == item.start and child.end == item.end
    if parent is not None:
        # Binarization/recursion nodes encode a flat reference constituent.
        if (
            item.category == "NP" and parent.category == "NP"
            and parent.rule_id in {"np_relative_subj", "np_relative_obj", "np_pp_mod", "np_pp"}
        ):
            skip = True
        if (
            item.category == "VP" and parent.category == "VP"
            and parent.rule_id in {"vp_pp", "vp_adv", "advp_vp"}
        ):
            skip = True
        if item.category == "VP" and parent.rule_id == "clause_neg_vp":
            skip = True
        if item.category == "VP-NP" and parent.rule_id in {
            "vp_modal_bare", "clause_yn", "clause_yn_neg", "clause_neg",
        }:
            # The reference keeps modal/do support in one VP; the parser's
            # VP-NP is the structurally useful bare-predicate layer.
            skip = True
    out: Counter[tuple[str, int, int]] = Counter()
    if category == "QMARK":
        skip = True  # Reference root spans deliberately exclude final punctuation.
    if not skip:
        normalized_end = item.end
        if item.category == "CLAUSE" and item.children and item.children[-1].category == "QMARK":
            normalized_end = item.children[-1].start
        out[(category, normalized_start, normalized_end)] += 1
    if item.rule_id in {"clause_there", "clause_there_pp"}:
        # Existentials are flat in the parser so the expletive/pivot relation
        # stays directly visible.  The reference additionally wraps COPULA +
        # pivot (+ PP) in VP; project only that representational wrapper.
        out[("VP", item.children[1].start, item.end)] += 1
    next_ancestors = ancestors + (item,)
    for child in item.children:
        out.update(normalized_parser(child, item, next_ancestors))
    return out


def PRF(expected: Counter[Any], actual: Counter[Any]) -> dict[str, Any]:
    matched = sum((expected & actual).values())
    expected_count = sum(expected.values())
    actual_count = sum(actual.values())
    precision = matched / actual_count if actual_count else 0.0
    recall = matched / expected_count if expected_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "exact": expected == actual,
        "matched": matched,
        "expected": expected_count,
        "actual": actual_count,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def lexical_score(row: dict[str, Any], best: Any | None) -> dict[str, Any]:
    expected = {
        tuple(token["span"]): token["pos"]
        for token in row["tokens"]
        if token["pos"] != "PUNCT" or token["span"][1] <= row["tree"]["span"][1]
    }
    selected: dict[tuple[int, int], str] = {}
    if best is not None:
        for node in walk_parser(best):
            if node.lexical_candidate is not None:
                selected[(node.start, node.end)] = node.category
    details = []
    correct = 0
    for span, gold_category in expected.items():
        parser_category = selected.get(span)
        accepted = parser_category in LEXICAL_EQUIVALENTS.get(gold_category, {gold_category})
        correct += int(accepted)
        if not accepted:
            details.append({
                "span": list(span), "text": row["text"][span[0]:span[1]],
                "expected": gold_category, "actual": parser_category,
            })
    total = len(expected)
    return {"correct": correct, "total": total, "accuracy": round(correct / total, 6) if total else 1.0, "errors": details}


def _anchor_span(anchor: str | None) -> tuple[int, int] | None:
    if not anchor or not anchor.startswith("lex:"):
        return None
    parts = anchor.split(":", 4)
    return int(parts[1]), int(parts[2])


def _parser_head(item: Any) -> tuple[int, int] | None:
    preferred = ("event", "head", "referent") if item.category.startswith(("V", "CLAUSE", "WH")) else ("head", "referent", "event")
    for name in preferred:
        span = _anchor_span(item.syntax.anchors.get(name))
        if span is not None:
            return span
    return None


ROLE_MAP = {
    "subject": "subject", "object": "object", "iobj": "iobj",
    "ccomp": "ccomp", "xcomp": "xcomp", "advcl": "advcl",
    "acl:relcl": "acl", "nmod": "nmod", "possessor": "nmod:poss",
    "advmod": "advmod", "complement": "complement", "pivot": "pivot",
}


def _gold_head(node: dict[str, Any]) -> tuple[int, int] | None:
    if "token_id" in node:
        return tuple(node["span"])
    children = node.get("children", ())
    priorities = {
        "CLAUSE": ("cop", "predicate", "main", "content", "head"),
        "RELCLAUSE": ("content", "head"),
        "WH-CLAUSE": ("content", "head"),
        "VP": ("head", "predicate", "complement"),
        "VP-INF": ("head",), "VP-COORD": ("predicate",), "VP-LIST": ("predicate",),
        "NP": ("head",), "NP-GERUND": ("head",), "NP-COORD": ("head",), "NP-LIST": ("head",),
        "PP": ("case", "head"),
    }.get(node["category"], ("head", "content"))
    for role in priorities:
        for child in children:
            if child.get("role") == role:
                head = _gold_head(child)
                if head is not None:
                    return head
    for child in children:
        head = _gold_head(child)
        if head is not None:
            return head
    return None


def gold_relations(node: dict[str, Any]) -> Counter[tuple[str, tuple[int, int], tuple[int, int]]]:
    out: Counter[tuple[str, tuple[int, int], tuple[int, int]]] = Counter()
    governor = _gold_head(node)
    for child in node.get("children", ()):
        role = child.get("role", "")
        normalized = ROLE_MAP.get(role)
        if normalized is None and role.startswith("obl"):
            normalized = "obl"
        dependent = _gold_head(child)
        if normalized and governor and dependent and governor != dependent:
            out[(normalized, governor, dependent)] += 1
        out.update(gold_relations(child))
    return out


def parser_relations(item: Any | None) -> Counter[tuple[str, tuple[int, int], tuple[int, int]]]:
    out: Counter[tuple[str, tuple[int, int], tuple[int, int]]] = Counter()
    if item is None:
        return out
    governor = _parser_head(item)
    for link in item.syntax.links:
        if link.child_index is None or link.child_index >= len(item.children):
            continue
        child = item.children[link.child_index]
        relation = link.relation
        normalized = None
        if relation == "subject": normalized = "subject"
        elif relation == "theme" and item.rule_id in {"clause_there", "clause_there_pp"}: normalized = "pivot"
        elif relation in {"object", "theme"} and item.category.startswith("VP"): normalized = "object"
        elif relation == "recipient": normalized = "obl" if child.category.startswith("PP") else "iobj"
        elif relation in {"comp", "clause"}: normalized = "ccomp"
        elif relation in {"inf", "xcomp"}: normalized = "xcomp"
        elif relation == "relative": normalized = "acl"
        elif relation == "adv": normalized = "advmod"
        elif relation in {"adjunct", "mod", "complement"}:
            normalized = "nmod" if item.category == "NP" and child.category.startswith("PP") else ("obl" if child.category.startswith("PP") else "complement")
        dependent = _parser_head(child)
        if normalized and governor and dependent and governor != dependent:
            out[(normalized, governor, dependent)] += 1
    for child in item.children:
        out.update(parser_relations(child))
    return out


def compact(counter: Counter[Any]) -> list[Any]:
    return [{"item": list(item), "count": count} for item, count in sorted(counter.items(), key=repr)]


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    rows = corpus["sentences"]
    parser = Parser.from_dir(args.data_dir, cache_size=0)
    parser.parse("The child laughed.").result.best()
    details = []
    aggregate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    durations = []

    for index, row in enumerate(rows, 1):
        started = perf_counter()
        result = parser.parse(row["text"]).result
        best = result.best()
        duration = (perf_counter() - started) * 1000
        durations.append(duration)
        raw = PRF(raw_gold(row["tree"]), raw_parser(best))
        normalized_expected = normalized_gold(row["tree"])
        normalized_actual = normalized_parser(best)
        normalized = PRF(normalized_expected, normalized_actual)
        lexical = lexical_score(row, best)
        expected_relations = gold_relations(row["tree"])
        actual_relations = parser_relations(best)
        relations = PRF(expected_relations, actual_relations)

        classification = "correct"
        search_class = None
        if best is None:
            classification = "coverage_failure"
        elif lexical["accuracy"] < 1:
            classification = "lexical_error"
        elif normalized["exact"] and not raw["exact"]:
            classification = "notation_only"
        elif relations["f1"] < 1:
            classification = "structural_or_attachment_error"
        elif not normalized["exact"]:
            classification = "constituency_representation_or_structure"

        # A wide diagnostic parse is intentionally opt-in: it can be slow.
        if args.diagnostic and classification not in {"correct", "notation_only"}:
            diagnostic = parser.parse_diagnostic(
                row["text"], alternatives=args.diagnostic_k,
                max_items=args.diagnostic_max_items,
            ).result
            alternatives = diagnostic.alternatives(limit=args.diagnostic_k)
            reachable = any(
                normalized_parser(candidate) == normalized_expected
                for candidate in alternatives
            )
            if reachable:
                search_class = "B_generable_but_misranked"
            elif diagnostic.stats.get("budget_exceeded"):
                search_class = "C_pruned_or_budget_limited"
            else:
                # A finite k-best view cannot prove that the packed forest
                # contains no matching derivation.  Keep the A/B/C split
                # useful without overstating what this bounded audit saw.
                search_class = "A_not_found_in_diagnostic_top_k"

        detail = {
            "id": row["id"], "split": row["split"], "group": row["category"],
            "phenomena": row["phenomena"], "text": row["text"],
            "complete": best is not None, "duration_ms": round(duration, 4),
            "raw_constituents": raw, "normalized_constituents": normalized,
            "lexical_categories": lexical, "relations": relations,
            "classification": classification, "search_class": search_class,
            "budget_exceeded": bool(result.stats.get("budget_exceeded")),
            "strict_excluded": any(
                note.get("status") == "excluded_from_strict_evaluation"
                for note in row.get("reference_review", ())
            ),
            "raw_expected_only": compact(raw_gold(row["tree"]) - raw_parser(best)),
            "raw_parser_only": compact(raw_parser(best) - raw_gold(row["tree"])),
            "normalized_expected_only": compact(normalized_expected - normalized_actual),
            "normalized_parser_only": compact(normalized_actual - normalized_expected),
        }
        details.append(detail)
        aggregate[row["category"]].append(detail)
        if index % 25 == 0:
            print(f"evaluated {index}/{len(rows)}", flush=True)

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(items)
        return {
            "sentences": count,
            "coverage": sum(row["complete"] for row in items) / count if count else 0,
            "raw_exact": sum(row["raw_constituents"]["exact"] for row in items) / count if count else 0,
            "raw_constituent_f1": statistics.fmean(row["raw_constituents"]["f1"] for row in items) if items else 0,
            "normalized_exact": sum(row["normalized_constituents"]["exact"] for row in items) / count if count else 0,
            "normalized_constituent_f1": statistics.fmean(row["normalized_constituents"]["f1"] for row in items) if items else 0,
            "lexical_accuracy": sum(row["lexical_categories"]["correct"] for row in items) / max(1, sum(row["lexical_categories"]["total"] for row in items)),
            "relation_f1": statistics.fmean(row["relations"]["f1"] for row in items) if items else 0,
            "classifications": dict(Counter(row["classification"] for row in items)),
            "search_classes": dict(Counter(row["search_class"] for row in items if row["search_class"])),
        }

    return {
        "format": "seman2-reference-evaluation-v2",
        "corpus": str(args.corpus),
        "normalization": {
            "leaf_aliases": LEAF_ALIASES,
            "rule_category_projection": RULE_CATEGORY,
            "transparent_reference_nodes": ["SBAR", "unary ADJP/ADVP", "subject-gap CLAUSE over VP"],
            "transparent_parser_nodes": ["recursive NP/VP binarization", "unary ADJP/ADVP"],
            "projected_equivalences": [
                "TO + VP-NP under a control verb = VP-INF",
                "flat existential predicate = reference VP wrapper",
                "bare VP-NP under modal/do support = transparent predicate layer",
            ],
            "principle": "Raw trees are never modified; normalization removes only documented representational wrappers.",
        },
        "overall": summarize(details),
        "strict_overall": summarize([row for row in details if not row["strict_excluded"]]),
        "by_group": {key: summarize(value) for key, value in sorted(aggregate.items())},
        "performance_ms": {
            "median": statistics.median(durations), "total": sum(durations), "max": max(durations),
        },
        "details": details,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "seman2_reference_300_compact.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "superparser" / "data")
    ap.add_argument("--output", type=Path, default=ROOT / "data" / "reference_300_evaluation.json")
    ap.add_argument("--diagnostic", action="store_true")
    ap.add_argument("--diagnostic-k", type=int, default=64)
    ap.add_argument("--diagnostic-max-items", type=int, default=500_000)
    args = ap.parse_args()
    report = evaluate(args)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, indent=2))


if __name__ == "__main__":
    main()
