"""Replay the pre-cohesion 500 source anchors through the current segmenter.

Unlike a freshly sampled cohort, this experiment starts from the SAME 500
source locations and maps each old unit to the current analysis unit in the
SAME Gutenberg paragraph. It reports merges and long units separately.
No legacy splitting code is imported, no text from the novels is checked in.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import zip_longest
import json
from pathlib import Path
import re

from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, CHAPTER, analysis_units
from scripts.diagnose_novel_parses import run, STATUSES
from seman_parser.segmentation import tokenize
from seman_parser.sentence_boundaries import has_final_punctuation
from seman_parser.structural_preanalysis import analyze_paragraph

OLD_SHA = "851878102fb4305edbbe3530b54b33fdc22af82428773440f4dd35111c6d1d77"
CENSORED = frozenset({
    "timeout", "error", "forest_budget_exceeded", "kbest_budget_exceeded",
    "both_budgets_exceeded",
})


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _compact(text: str) -> str:
    """Whitespace-insensitive only; never normalize characters or punctuation."""
    return re.sub(r"\s+", "", text)


def find_anchor(source: str, paragraph_units: list[dict], old_ordinal: int) -> tuple[dict, str]:
    """Select an actual current source span containing the previous unit.

    Only candidates from the original paragraph are allowed. A tie in the
    nearest old ordinal is an error, not permission to choose randomly.
    """
    key = _compact(source)
    matches = [
        (row, "exact" if _compact(row["source_text"]) == key else "merged")
        for row in paragraph_units if key in _compact(row["source_text"])
    ]
    if not matches:
        raise ValueError(f"No current source unit contains the original anchor: {source!r}")
    matches.sort(key=lambda pair: (pair[1] != "exact",
                                   abs(pair[0]["ordinal"] - old_ordinal),
                                   pair[0]["ordinal"]))
    if len(matches) >= 2 and (
        matches[0][1] == matches[1][1]
        and abs(matches[0][0]["ordinal"] - old_ordinal)
        == abs(matches[1][0]["ordinal"] - old_ordinal)
    ):
        raise ValueError("Ambiguous same-paragraph source anchor " + repr(source))
    return matches[0]


def _paragraph_ordinals(core: str) -> list[int]:
    """Mirror the public source-unit stream, retaining paragraph identity."""
    result = []
    for pidx, paragraph in enumerate(re.split(r"\n\s*\n", core.replace("\r\n", "\n"))):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines or CHAPTER.match(lines[0]):
            continue
        joined = re.sub(r"\s+", " ", " ".join(lines))
        if not has_final_punctuation(joined) and (joined.isupper() or len(joined) < 45):
            continue
        result.extend([pidx] * len(analyze_paragraph(joined)))
    return result


def _current_paragraph_units(book) -> dict[int, list[dict]]:
    core, _ = load_cleaned(book)
    paragraph_ids = _paragraph_ordinals(core)
    paragraphs = defaultdict(list)
    raw_stream = analysis_units(core)
    balanced_stream = analysis_units(core, balance_sentence_quotes=True)
    count = 0
    for ordinal, (raw, balanced) in enumerate(zip_longest(raw_stream, balanced_stream)):
        if raw is None or balanced is None or raw.source_text != balanced.source_text:
            raise AssertionError("Quote transfer altered the source-unit stream")
        if ordinal >= len(paragraph_ids):
            raise AssertionError("Paragraph mapping ended before units")
        paragraphs[paragraph_ids[ordinal]].append({
            "book_id": book.ebook_id, "author": book.author,
            "ordinal": ordinal, "text": raw.text,
            "source_text": raw.source_text, "tokens": len(tokenize(raw.text)),
            "semicolon_split": raw.semicolon_split,
            "synthetic_prefix": raw.synthetic_prefix,
            "synthetic_suffix": raw.synthetic_suffix,
            "synthetic_terminal": raw.synthetic_terminal,
            "balanced_analysis_text": balanced.text,
            "balanced_synthetic_prefix": balanced.synthetic_prefix,
            "balanced_synthetic_suffix": balanced.synthetic_suffix,
            "balanced_synthetic_terminal": balanced.synthetic_terminal,
            "eligible_for_parse": raw.eligible_for_parse,
            "quotation_status": raw.quotation_status,
            "structural_status": raw.structural_status,
            "constituent_functions": [c.function for c in raw.constituents],
            "structural_paragraph_index": raw.paragraph_index,
            "structural_core_source_span": [raw.core_start, raw.core_end],
        })
        count += 1
    if count != len(paragraph_ids):
        raise AssertionError(f"Paragraph map disagrees with extractor for {book.ebook_id}")
    return paragraphs


def select_anchored(baseline_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Return exactly 500 current units and the one-to-one anchor evidence."""
    original_bytes = (baseline_dir / "cohort.jsonl").read_bytes()
    observed_sha = sha256(original_bytes).hexdigest()
    if observed_sha != OLD_SHA:
        raise ValueError(f"Wrong pre-cohesion reference artifact: {observed_sha}")
    old = _read_jsonl(baseline_dir / "cohort.jsonl")
    old_results = _read_jsonl(baseline_dir / "per_sentence.jsonl")
    old_contexts = _read_jsonl(baseline_dir / "context_dependency.jsonl")
    if len(old) != len(old_results) or len(old) != len(old_contexts) or len(old) != 500:
        raise ValueError("Pre-cohesion artifact must contain three aligned 500-row files")
    for i, (anchor, result, context) in enumerate(zip(old, old_results, old_contexts)):
        if (
            anchor["index"] != i or result["index"] != i or context["index"] != i
            or any(other["book_id"] != anchor["book_id"] for other in (result, context))
            or result["source_text"] != anchor["source_text"]
            or context["source_text"] != anchor["source_text"]
            or result["status"] not in STATUSES
        ):
            raise ValueError(f"Pre-cohesion anchor misaligned at {i}")
    books = {b.ebook_id: b for b in TRAIN_BOOKS}
    current = {bid: _current_paragraph_units(books[bid])
               for bid in sorted({r["book_id"] for r in old})}
    selected = []
    mapping = []
    for i, (anchor, result, context) in enumerate(zip(old, old_results, old_contexts)):
        pidx = context["context"]["paragraph_index"]
        candidate, kind = find_anchor(
            anchor["source_text"], current[anchor["book_id"]].get(pidx, []),
            anchor["ordinal"],
        )
        # The original stratification stays unchanged for a paired comparison.
        selected.append({**candidate, "band": anchor["band"]})
        mapping.append({
            "index": i, "book_id": anchor["book_id"],
            "paragraph_index": pidx,
            "old_ordinal": anchor["ordinal"],
            "new_ordinal": candidate["ordinal"],
            "original_band": anchor["band"],
            "old_tokens": anchor["tokens"], "new_tokens": candidate["tokens"],
            "old_source_text": anchor["source_text"],
            "new_source_text": candidate["source_text"],
            "kind": kind, "old_status": result["status"],
            "old_completed": result["completed"],
            "current_eligible_for_parse": candidate["eligible_for_parse"],
            "current_quotation_status": candidate["quotation_status"],
            "current_structural_status": candidate["structural_status"],
            "grammatical_functions": candidate["constituent_functions"],
            "current_book_span": candidate["structural_core_source_span"],
        })
    return selected, mapping, old_results


def compare(mapping: list[dict], new_rows: list[dict]) -> dict:
    if len(mapping) != 500 or len(new_rows) != 500:
        raise ValueError("A paired 500-anchor comparison is mandatory")
    transitions = Counter()
    by_kind = defaultdict(Counter)
    changes = []
    for m, n in zip(mapping, new_rows):
        if m["index"] != n["index"] or m["new_source_text"] != n["source_text"]:
            raise AssertionError("Current parse result is not aligned to its source anchor")
        if n["status"] not in STATUSES:
            raise ValueError("Unknown status in current diagnostics")
        k = m["kind"]
        before, after = m["old_status"], n["status"]
        transitions[(before, after)] += 1
        by_kind[k]["total"] += 1
        by_kind[k]["previous_complete"] += int(before == "complete")
        by_kind[k]["current_complete"] += int(after == "complete")
        by_kind[k]["unchanged_status"] += int(before == after)
        by_kind[k]["longer_than_32_tokens"] += int(m["new_tokens"] > 32)
        if before != after:
            changes.append({
                "index": m["index"], "kind": k,
                "before": before, "after": after,
                "old_source": m["old_source_text"],
                "new_source": m["new_source_text"],
                "old_tokens": m["old_tokens"], "new_tokens": m["new_tokens"],
            })
    distinct = {(m["book_id"], m["new_ordinal"]) for m in mapping}
    return {
        "schema": "seman2-anchored-500-structural-v1",
        "method": "same 500 source anchors and paragraphs; current production splitter; same parser and budgets",
        "previous_cohort_sha256": OLD_SHA,
        "anchor_count": 500,
        "distinct_current_analysis_units": len(distinct),
        "duplicate_anchor_destinations": 500 - len(distinct),
        "old_completed": sum(m["old_status"] == "complete" for m in mapping),
        "new_completed_by_anchor": sum(r["status"] == "complete" for r in new_rows),
        "mapping": {key: dict(value) for key, value in by_kind.items()},
        "status_transitions": [
            {"before": a, "after": b, "count": n}
            for (a, b), n in sorted(transitions.items())
        ],
        "changed_status_count": len(changes),
        "changed_status_examples": changes[:40],
        "limitations": [
            "Merged units contain additional original source; a different parse status is not a grammar regression or an automatically corrected tree.",
            "Some old anchors may point to the same new unit; by-anchor totals count those anchors, not independent new sentences.",
            "The 4x4 book/length strata are from the previous cohort; new merged units may now exceed 32 tokens.",
            "A complete result is not certified to have the correct ranked grammatical tree.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-dir", type=Path, required=True)
    p.add_argument("--wordnet-dir", type=Path)
    p.add_argument("--mapping-only", action="store_true",
                   help="Compare source spans and grammatical roles; do not claim parser scores")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--max-items", type=int, default=50_000)
    p.add_argument("--kbest-work-limit", type=int, default=500_000)
    p.add_argument("--deadline-seconds", type=float, default=10)
    args = p.parse_args()
    selected, mapping, old = select_anchored(args.baseline_dir)
    args.count = len(selected)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "anchor_mapping.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in mapping),
        encoding="utf-8",
    )
    print("ANCHORED_MAPPING", json.dumps({
        "count": len(mapping),
        "exact": sum(m["kind"] == "exact" for m in mapping),
        "merged": sum(m["kind"] == "merged" for m in mapping),
        "new_over_32_tokens": sum(m["new_tokens"] > 32 for m in mapping),
        "unique": len({(m["book_id"], m["new_ordinal"]) for m in mapping}),
    }), flush=True)
    if args.mapping_only:
        result = {
            "schema": "seman2-anchored-500-source-completeness-v2",
            "method": "same original 500 source anchors remapped in the same original paragraphs",
            "previous_cohort_sha256": OLD_SHA,
            "anchor_count": len(mapping),
            "exact": sum(m["kind"] == "exact" for m in mapping),
            "reconstructed_complete": sum(m["current_eligible_for_parse"] for m in mapping),
            "requires_source_context": sum(
                not m["current_eligible_for_parse"] for m in mapping),
            "old_failed_now_source_complete": sum(
                m["old_status"] != "complete" and m["current_eligible_for_parse"]
                for m in mapping),
            "source_extent_changed": sum(m["kind"] == "merged" for m in mapping),
            "distinct_current_analysis_units": len({
                (m["book_id"], m["new_ordinal"]) for m in mapping
            }),
            "with_original_quote_fabrication": 0,
            "typed_functions": dict(Counter(
                fn for m in mapping for fn in m["grammatical_functions"]
            )),
            "per_anchor": mapping,
            "interpretation": (
                "This is a SOURCE-STRUCTURE audit, not a before-after grammar "
                "coverage claim. Context-incomplete speech is never silently "
                "repaired. Full-parser outcomes require separately validated "
                "eligible source units and matched budgets."
            ),
        }
        (args.out_dir / "anchored_source_completeness.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("ANCHORED_SOURCE_COMPLETENESS", json.dumps({
            k: v for k, v in result.items() if k != "per_anchor"
        }, ensure_ascii=False), flush=True)
        return
    if args.wordnet_dir is None:
        raise ValueError("--wordnet-dir required for full parse mode")
    run(
        args,
        selected_override=selected,
        source_description="same original 500 source anchors, remapped to current source units",
    )
    result = compare(mapping, _read_jsonl(args.out_dir / "per_sentence.jsonl"))
    (args.out_dir / "anchored_comparison.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print("ANCHORED_COMPARISON", json.dumps({
        k: v for k, v in result.items() if k not in ("changed_status_examples", "status_transitions")
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
