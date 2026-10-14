#!/usr/bin/env python3
"""Write one compact expected-vs-parser tree report for the 300 references."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "superparser"))

from seman_parser import Parser  # noqa: E402
from scripts.evaluate_reference_300 import (  # noqa: E402
    PRF, normalized_gold, normalized_parser, raw_gold, raw_parser,
)


def gold_tree(node: dict) -> str:
    children = node.get("children", ())
    if not children:
        return f'{node["category"]}({json.dumps(node["text"], ensure_ascii=False)})'
    return f'{node["category"]}({", ".join(gold_tree(child) for child in children)})'


def parser_tree(item) -> str:
    if item is None:
        return "AUCUN_ARBRE"
    if item.lexical_candidate is not None:
        return f'{item.category}({json.dumps(item.lexical_candidate.surface, ensure_ascii=False)})'
    return f'{item.category}({", ".join(parser_tree(child) for child in item.children)})'


def main() -> None:
    corpus_path = ROOT / "data" / "seman2_reference_300_compact.json"
    destination = ROOT / "data" / "300_phrases_results.txt"
    temporary = destination.with_suffix(".txt.tmp")
    rows = json.loads(corpus_path.read_text(encoding="utf-8"))["sentences"]
    parser = Parser.from_dir(ROOT / "superparser" / "data", cache_size=0)
    output = [
        "SUPERPARSER — BONNE RÉPONSE VS RÉPONSE DU PARSEUR",
        f"Phrases: {len(rows)}",
        "Notation: CATEGORIE(enfants...) ; les feuilles contiennent le mot.",
        "",
    ]
    complete = normalized_exact = 0
    print(f"Démarrage: {len(rows)} phrases -> {destination}", flush=True)
    for index, row in enumerate(rows, 1):
        best = parser.parse(row["text"]).result.best()
        raw = PRF(raw_gold(row["tree"]), raw_parser(best))
        normalized = PRF(normalized_gold(row["tree"]), normalized_parser(best))
        complete += best is not None
        normalized_exact += normalized["exact"]
        output.extend((
            f'[{row["id"]}] {row["text"]}',
            f'BONNE RÉPONSE : {gold_tree(row["tree"])}',
            f'SUPERPARSER    : {parser_tree(best)}',
            (
                f'STATUT         : {"COMPLET" if best else "INCOMPLET"}'
                f' | EXACT BRUT: {"OUI" if raw["exact"] else "NON"}'
                f' | EXACT NORMALISÉ: {"OUI" if normalized["exact"] else "NON"}'
                f' | F1 NORMALISÉ: {normalized["f1"]:.6f}'
            ),
            "",
        ))
        if index % 10 == 0:
            print(f"Progression: {index}/{len(rows)}", flush=True)
    output[2:2] = [
        f"Couverture: {complete}/{len(rows)}",
        f"Arbres exacts normalisés: {normalized_exact}/{len(rows)}",
    ]
    temporary.write_text("\n".join(output), encoding="utf-8")
    temporary.replace(destination)
    print(
        f"Terminé: couverture {complete}/{len(rows)}, "
        f"exacts normalisés {normalized_exact}/{len(rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
