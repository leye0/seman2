"""Audit actual syntactic trees for pinned novel cases, not only completion.

Uses the same 500-case extraction and the same public Parser.parse gateway as
the official diagnostic; a row is never re-tokenized or quote-normalized here.
Run with: PYTHONPATH=superparser python -m scripts.audit_novel_tree_quality
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from scripts.diagnose_novel_parses import select_cases
from seman_parser.engine import Parser, ParserResources

DATA = Path(__file__).resolve().parents[1] / "data"
TARGETS = (107, 328, 368, 480)


def display_tree(item, text: str, depth: int = 0) -> list[str]:
    """One node per line with source spans so suspicious attachments are visible."""
    fragment = text[item.start:item.end].replace("\n", " ")
    if len(fragment) > 100:
        fragment = fragment[:97] + "..."
    label = item.rule_id if item.rule_id is not None else "<lexical>"
    lines = [f"{'  ' * depth}{item.category:15} {label:42} "
             f"[{item.start}:{item.end}] {fragment!r}"]
    for child in item.children:
        lines.extend(display_tree(child, text, depth + 1))
    return lines

def display_lexical_matrix(lattice, *, index: int) -> None:
    """Report ALL category/feature hypotheses at their exact token positions.

    Include source and sense provenance; no lexical alternative is silently
    reduced to one best POS tag. Multiword candidates are shown separately.
    """
    for token in lattice.tokens:
        candidates = sorted(
            lattice.covering(token.start, token.end),
            key=lambda candidate: (
                candidate.category, -candidate.score, candidate.source,
                candidate.sense_id or "",
            ),
        )
        print("NOVEL_LEXICAL_MATRIX", json.dumps({
            "case_index": index, "token_index": token.index,
            "text": token.text, "start": token.start, "end": token.end,
            "candidates": [{
                "category": c.category, "features": c.features.as_dict(),
                "source": c.source, "sense_ids": c.sense_ids,
                "score": c.score,
            } for c in candidates],
        }, ensure_ascii=False), flush=True)
    for candidate in lattice.candidates:
        if not any(
            token.start == candidate.span_start and
            token.end == candidate.span_end for token in lattice.tokens
        ):
            print("NOVEL_MULTIWORD_MATRIX", json.dumps({
                "case_index": index, "start": candidate.span_start,
                "end": candidate.span_end, "surface": candidate.surface,
                "category": candidate.category,
                "features": candidate.features.as_dict(),
                "source": candidate.source,
            }, ensure_ascii=False), flush=True)



def audit(indices: tuple[int, ...], *, wordnet_dir: str | None,
          max_items: int, kbest_work_limit: int, alternatives: int,
          lexical_audit: bool = False) -> None:
    selected, _ = select_cases(500)
    if len(selected) != 500:
        raise AssertionError("Pinned cohort lost entries")
    resources = ParserResources.from_dir(DATA, wordnet_dict=wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=max_items)
    for idx in indices:
        if idx < 0 or idx >= len(selected):
            raise ValueError(f"Out-of-range cohort index {idx}")
        case = selected[idx]
        prepared, lattice, result = parse_corpus_case(
            parser, case, max_items=max_items,
            kbest_work_limit=kbest_work_limit,
        )
        print("NOVEL_TREE_AUDIT", json.dumps({
            "index": idx, "book_id": case["book_id"],
            "source": case["text"],
            "analysis": prepared.analysis_text,
            "completed": result.completed,
            "root_rule": result.best().rule_id if result.best() else None,
            "forest_nodes": result.stats.get("forest_nodes"),
            "budget_exceeded": result.stats.get("budget_exceeded"),
            "lexical_candidates": len(lattice.candidates),
        }, ensure_ascii=False), flush=True)
        if lexical_audit:
            display_lexical_matrix(lattice, index=idx)
        for rank, item in enumerate(result.alternatives(limit=alternatives)):
            print(f"NOVEL_TREE_BEGIN index={idx} rank={rank + 1} score={item.score:.4f}",
                  flush=True)
            print("\n".join(display_tree(item, result.text)), flush=True)
            print(f"NOVEL_TREE_END index={idx} rank={rank + 1}", flush=True)


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--indices", default=",".join(map(str, TARGETS)))
    args.add_argument("--wordnet-dir", default=None)
    args.add_argument("--max-items", type=int, default=50_000)
    args.add_argument("--kbest-work-limit", type=int, default=500_000)
    args.add_argument("--alternatives", type=int, default=2)
    args.add_argument("--lexical-audit", action="store_true")
    opts = args.parse_args()
    audit(tuple(int(x) for x in opts.indices.split(",") if x.strip()),
          wordnet_dir=opts.wordnet_dir, max_items=opts.max_items,
          kbest_work_limit=opts.kbest_work_limit,
          alternatives=opts.alternatives,
          lexical_audit=opts.lexical_audit)


if __name__ == "__main__":
    main()
