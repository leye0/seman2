"""Audit v2 semicolon-dependent prose with the canonical corpus parser.

This is a *prospective* four-passage diagnostic, not the SHA-pinned 500-case
benchmark. It reports actual rank-one trees, spans and semicolon ancestors.
No hand-coded grammar decision or score is treated as proof of correctness.

Run with:
    PYTHONPATH=superparser python -m scripts.audit_semicolon_context \
        --wordnet-dir /path/to/wordnet3/dict
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from research.verbnet_lr.gutenberg_novels import Book, extract
from seman_parser.engine import Parser, ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Passage:
    frozen_index: int
    ebook_id: int
    title: str
    source: str
    expected_dependency: str


PASSAGES = (
    Passage(
        8, 766, "David Copperfield",
        "I could do no less, under these circumstances, than make Mr. "
        "Micawber known to Uriah Heep and his mother; which I accordingly did.",
        "sentential_which_relative_refers_to_preceding_event",
    ),
    Passage(
        94, 766, "David Copperfield",
        "She gently chid me for being rude; and, keeping me close to her "
        "shawl, turned to thank the gentleman for taking so much trouble "
        "as to bring her home.",
        "chid_and_turned_share_subject_she",
    ),
    Passage(
        182, 1342, "Pride and Prejudice",
        "He found her as handsome as she had been last year; as good "
        "natured, and as unaffected, though not quite so chatty.",
        "parallel_comparatives_modify_found_her",
    ),
    Passage(
        194, 1342, "Pride and Prejudice",
        "To the rest of the family they paid little attention; avoiding "
        "Mrs. Bennet as much as possible, saying not much to Elizabeth, "
        "and nothing at all to the others.",
        "avoiding_and_saying_are_nonfinite_adjuncts",
    ),
)


def _selected_tree(item, text: str):
    return {
        "category": item.category,
        "rule_id": item.rule_id,
        "span": [item.start, item.end],
        "source": text[item.start:item.end],
        "children": [_selected_tree(child, text) for child in item.children],
    }


def _semicolon_ancestor_path(item, position: int):
    """Return exact selected nodes from the root to the semicolon leaf."""
    if not item.start <= position < item.end:
        return None
    current = [item.category, item.rule_id, item.start, item.end]
    for child in item.children:
        path = _semicolon_ancestor_path(child, position)
        if path is not None:
            return [current, *path]
    return [current]


def _attachment_warnings(item, position: int):
    """Flag suspicious punctuation scope, without certifying any good tree.

    These are *necessary* contextual checks for the four source passages,
    not a semantic evaluator. A tree with no warnings still needs expert
    parent/child and agreement inspection.
    """
    if item is None:
        return ["no_selected_root"]
    path = _semicolon_ancestor_path(item, position)
    if path is None:
        return ["semicolon_missing_from_selected_tree"]
    flags = []
    # A semicolon joining sentence-level material must not be swallowed as
    # an apposition inside a prepositional or nominal complement.
    for category, rule_id, _start, _end in path[:-1]:
        if category == "NP" and rule_id is not None:
            flags.append("semicolon_scoped_inside_nominal_constituent")
        if category == "NP" and rule_id == "np_appos_comma":
            flags.append("semicolon_consumed_by_nominal_apposition")
        if category == "VP" and rule_id in {"vp_comma_coord", "vp_comma_list"}:
            flags.append("semicolon_consumed_by_comma_vp_coordination")
    return list(dict.fromkeys(flags))


def _diagnostic_status(*, completed: bool, budget_exceeded: bool,
                       attachment_warnings: list[str]) -> str:
    """Never mistake coverage, a provisional tree or an empty flag list for quality."""
    if not completed:
        return "no_complete_tree"
    if budget_exceeded:
        return "resource_censored_tree"
    if attachment_warnings:
        return "structurally_suspect_tree"
    return "uncertified_complete_tree"


def audit(*, wordnet_dir: str | None = None, max_items: int = 50_000,
          kbest_work_limit: int = 500_000, summary_only: bool = False):
    resources = ParserResources.from_dir(DATA, wordnet_dict=wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=max_items)
    has_wordnet = resources.lexicon.has_wordnet
    for passage in PASSAGES:
        book = Book(passage.ebook_id, passage.title, "Seman2 fixture", "train")
        rows, _ = extract(
            book, passage.source, length_min=1, length_max=100,
            segmentation_version=2,
        )
        if len(rows) != 1 or rows[0]["source_text"] != passage.source:
            raise AssertionError(
                f"v2 lost source context for frozen case {passage.frozen_index}"
            )
        prepared, lattice, result = parse_corpus_case(
            parser, rows[0], max_items=max_items,
            kbest_work_limit=kbest_work_limit,
        )
        if prepared.source_text != passage.source:
            raise AssertionError("Mandatory corpus parsing gateway lost provenance")
        best = result.best()
        marker = prepared.analysis_text.find(";")
        record = {
            "frozen_index": passage.frozen_index,
            "segmentation_version": 2,
            "wordnet_loaded": has_wordnet,
            "canonical_baseline_comparable": False,
            "parse_mode": prepared.mode.value,
            "expected_dependency": passage.expected_dependency,
            "source_text": prepared.source_text,
            "analysis_text": prepared.analysis_text,
            "tokens": len(lattice.tokens),
            "completed": result.completed,
            "forest_nodes": result.stats.get("forest_nodes"),
            "partial_states": result.stats.get("partial_states"),
            "budget_exceeded": result.stats.get("budget_exceeded"),
            "selected_root_rule": best.rule_id if best else None,
            "attachment_warnings": _attachment_warnings(best, marker),
            "semicolon_selected_path": (
                _semicolon_ancestor_path(best, marker)
                if best is not None and marker >= 0 else None
            ),
            "selected_tree": (
                _selected_tree(best, prepared.analysis_text)
                if best is not None else None
            ),
        }
        record["diagnostic_status"] = _diagnostic_status(
            completed=result.completed,
            budget_exceeded=bool(result.stats.get("budget_exceeded")),
            attachment_warnings=record["attachment_warnings"],
        )
        if summary_only:
            record.pop("selected_tree")
            record.pop("semicolon_selected_path")
        print(json.dumps(record, ensure_ascii=False), flush=True)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--wordnet-dir", default=None)
    args.add_argument("--max-items", type=int, default=50_000)
    args.add_argument("--kbest-work-limit", type=int, default=500_000)
    args.add_argument("--summary-only", action="store_true",
                      help="one compact JSON record per case for CI logs")
    settings = args.parse_args()
    audit(wordnet_dir=settings.wordnet_dir, max_items=settings.max_items,
          kbest_work_limit=settings.kbest_work_limit,
          summary_only=settings.summary_only)


if __name__ == "__main__":
    main()
