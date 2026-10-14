#!/usr/bin/env python3
"""Reproducible manual-plausibility sample for Predictive V2 divergences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from scripts.evaluate_reference_300 import PRF, normalized_gold, normalized_parser  # noqa: E402
from scripts.generate_reference_300_results import gold_tree, parser_tree  # noqa: E402
from seman_parser.predictive import HybridPredictiveParser, TransitionModel  # noqa: E402


# Human judgments are deliberately explicit rather than inferred from F1.
# They are filled after inspecting the emitted tree, its features and its rules.
JUDGMENTS: dict[str, tuple[str, str]] = {
    "SEM-GOLD-228": ("INVALID", "The object relative is missed; Lena is incorrectly absorbed as the head noun."),
    "SEM-GOLD-216": ("INVALID", "The preposition in is analysed as a noun and creates an unsupported second object."),
    "SEM-GOLD-201": ("UNCERTAIN", "A coordinated-predicate reading is formally licensed, but lexical valence makes it very doubtful here."),
    "SEM-GOLD-205": ("UNCERTAIN", "A coordinated-predicate reading is formally licensed, but the intended noun list is overwhelmingly preferable."),
    "SEM-GOLD-092": ("VALID_ALTERNATIVE", "Before dinner is a sentential temporal adjunct instead of a VP adjunct."),
    "SEM-GOLD-097": ("VALID_ALTERNATIVE", "Before noon is a sentential temporal adjunct instead of a VP adjunct."),
    "SEM-GOLD-099": ("INVALID", "At is consumed inside a noun compound instead of introducing the temporal PP."),
    "SEM-GOLD-264": ("VALID", "Driver's license is recognised as a single lexical compound; the clause structure is sound."),
    "SEM-GOLD-297": ("INVALID", "Several PP tokens are folded into a spurious relative/gap construction."),
    "SEM-GOLD-042": ("INVALID", "Missing ditransitive valence for sent forces an impossible compound object."),
    "SEM-GOLD-043": ("INVALID", "The recipient and theme are collapsed into an impossible compound object."),
    "SEM-GOLD-044": ("INVALID", "The recipient and theme are collapsed into an impossible compound object."),
    "SEM-GOLD-220": ("INVALID", "After is treated as an adjective inside the object NP rather than as an adjunct."),
    "SEM-GOLD-219": ("VALID_ALTERNATIVE", "Before sunset attaches to the completed clause; the attachment remains grammatical."),
    "SEM-GOLD-225": ("VALID_ALTERNATIVE", "Before rain attaches to the completed clause; the attachment remains grammatical."),
    "SEM-GOLD-066": ("INVALID", "In is analysed as a noun and the kitchen becomes an unsupported second object."),
    "SEM-GOLD-083": ("VALID_ALTERNATIVE", "Signed is analysed as a predicative adjective; the passive reading remains an alternative."),
    "SEM-GOLD-284": ("VALID", "The object-gap relative and project adjunct are preserved despite different internal grouping."),
    "SEM-GOLD-272": ("VALID_ALTERNATIVE", "The locative PP modifies the existential NP rather than the predicate."),
    "SEM-GOLD-223": ("VALID_ALTERNATIVE", "Both temporal PPs attach inside the object NP; this is syntactically possible though dispreferred."),
}


def _walk(item: Any) -> list[Any]:
    return [item] + [node for child in item.children for node in _walk(child)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "seman2_reference_300_compact.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "superparser" / "data")
    ap.add_argument("--model", type=Path, default=ROOT / "superparser" / "data" / "predictive_transitions.json")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--candidates", type=int, default=30)
    args = ap.parse_args()
    rows = json.loads(args.corpus.read_text(encoding="utf-8"))["sentences"]
    parser = HybridPredictiveParser.from_dir(
        args.data_dir, model=TransitionModel.load(args.model), max_states=50_000,
        fast_states=64, lookahead=1,
    )
    parser.parse("Warm engines turn.")
    divergences = []
    for row in rows:
        result = parser.parse(row["text"])
        if not result.item:
            continue
        score = PRF(normalized_gold(row["tree"]), normalized_parser(result.item))
        if score["exact"]:
            continue
        nodes = _walk(result.item)
        divergences.append({
            "id": row["id"], "text": row["text"], "f1": score["f1"],
            "gold": gold_tree(row["tree"]), "predictive": parser_tree(result.item),
            "rules": [node.rule_id for node in nodes if node.rule_id],
            "finite_clauses": sum(
                node.category == "CLAUSE" and node.features.get("finite") == "yes"
                for node in nodes
            ),
            "judgment": JUDGMENTS.get(row["id"], ("UNREVIEWED", "manual review pending"))[0],
            "reason": JUDGMENTS.get(row["id"], ("UNREVIEWED", "manual review pending"))[1],
        })
    ranked = sorted(divergences, key=lambda row: (row["f1"], row["id"]))
    # Low-F1 failures plus a deterministic spread prevents cherry-picking only
    # near-exact PP attachments.
    selected = ranked[: min(15, len(ranked))]
    remainder = ranked[len(selected):]
    if remainder:
        stride = max(1, len(remainder) // max(1, args.candidates - len(selected)))
        selected += remainder[::stride][: args.candidates - len(selected)]
    payload = {
        "format": "seman2-predictive-v2-plausibility-audit-v1",
        "selection": "15 lowest normalized F1 plus deterministic spread of remaining divergences",
        "total_divergences": len(divergences),
        "cases": selected,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
