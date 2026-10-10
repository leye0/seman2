#!/usr/bin/env python3
"""Run the first incremental grammar-induction experiment on the novel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from research.induction.grammar_induction import GrammarHypothesisRegistry, observe_parse
from seman_parser import Parser
from seman_parser.coverage import extract_sentences


def quantile(values, ratio):
    return sorted(values)[round((len(values) - 1) * ratio)] if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=500)
    parser.add_argument("--validation", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    corpus = ROOT.parent / "data" / "the_map_of_everything_nlp_novel.txt"
    cases = extract_sentences(corpus, limit=args.train + args.validation)
    engine = Parser.from_dir(ROOT / "data", cache_size=0)
    engine.parse("The woman opened a box.")
    registry = GrammarHypothesisRegistry(engine.resources.grammar)
    parse_times = {"train": [], "validation": []}
    ingestion_times = {"train": [], "validation": []}
    completed = {"train": 0, "validation": 0}
    observation_totals = {"forest_nodes": 0, "forest_derivations": 0, "gaps": 0}

    started = perf_counter()
    for index, case in enumerate(cases):
        split = "train" if index < args.train else "validation"
        parse_started = perf_counter()
        result = engine.parse(case.text).result
        parse_times[split].append((perf_counter() - parse_started) * 1000)
        completed[split] += int(result.completed)
        observation = observe_parse(f"novel-{case.index}", result, engine.resources.grammar)
        ingest_started = perf_counter()
        registry.ingest(observation, validation=split == "validation")
        ingestion_times[split].append((perf_counter() - ingest_started) * 1000)
        if split == "train":
            observation_totals["forest_nodes"] += observation.forest_nodes
            observation_totals["forest_derivations"] += observation.forest_derivations
            observation_totals["gaps"] += len(observation.gaps)
        if (index + 1) % 100 == 0:
            print(f"{index + 1}/{len(cases)}", flush=True)

    hypotheses = registry.hypotheses(min_support=3)
    top = hypotheses[:10]
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    registry_path = output / "hypothesis_registry.json"
    registry.save(registry_path)
    registry_bytes = registry_path.stat().st_size
    result = {
        "schema_version": "grammar-induction-experiment/0.1",
        "grammar_rule_count": len(engine.resources.grammar),
        "train_count": args.train,
        "validation_count": args.validation,
        "completed": completed,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "parse_ms": {
            split: {
                "median": round(statistics.median(values), 3),
                "p90": round(quantile(values, .9), 3),
            }
            for split, values in parse_times.items()
        },
        "ingestion_ms": {
            split: {
                "total": round(sum(values), 3),
                "median": round(statistics.median(values), 4),
                "p90": round(quantile(values, .9), 4),
            }
            for split, values in ingestion_times.items()
        },
        "observation_totals": observation_totals,
        "registry_bytes": registry_bytes,
        "hypothesis_count": len(hypotheses),
        "classification_counts": {
            name: sum(row.classification == name for row in hypotheses)
            for name in ("potential-new", "macro", "known-construction")
        },
        "top_hypotheses": [row.as_dict() for row in top],
    }
    (output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Première expérience d'induction grammaticale", "",
        f"Corpus : {args.train} phrases d'observation, puis {args.validation} phrases distinctes de validation.",
        f"Grammaire inchangée : {len(engine.resources.grammar)} règles.", "",
        "## Résultat", "",
        f"- Hypothèses retenues (support ≥ 3) : {len(hypotheses)}",
        f"- Nouvelles constructions fiables : {result['classification_counts']['potential-new']}",
        f"- Macros compositionnelles : {result['classification_counts']['macro']}",
        f"- Constructions directes connues : {result['classification_counts']['known-construction']}",
        f"- Registre persistant : {registry_bytes} octets",
        f"- Ingestion des 500 observations : {result['ingestion_ms']['train']['total']} ms",
        f"- Temps d'ingestion médian : {result['ingestion_ms']['train']['median']} ms par phrase",
        f"- Forêt observée : {observation_totals['forest_nodes']} constituants et {observation_totals['forest_derivations']} dérivations",
        f"- Segments non couverts conservés : {observation_totals['gaps']}",
        "- Gain de couverture mesuré : 0 (les hypothèses ne sont volontairement pas injectées)",
        "",
        "## Dix hypothèses les plus intéressantes", "",
    ]
    for number, hypothesis in enumerate(top, 1):
        lines.extend([
            f"### {number}. `{hypothesis.lhs} → {' '.join(hypothesis.rhs)}`", "",
            f"Classification : **{hypothesis.classification}**. Support observation : {hypothesis.support}; support validation : {hypothesis.validation_support}; gain de compression estimé : {hypothesis.compression_gain}.",
            f"Contraintes stables : `{json.dumps(dict(hypothesis.feature_constraints), ensure_ascii=False, sort_keys=True)}`.",
            f"Composition source : `{', '.join(hypothesis.rule_ids)}`.", "",
            "Exemples :", "",
            *[f"- {example}" for example in hypothesis.examples[:3]], "",
            "Exemples concurrents sur le même RHS :", "",
            *([f"- {example}" for example in hypothesis.counterexamples[:3]] or ["- Aucun dans la validation."]), "",
        ])
    if not result["classification_counts"]["potential-new"]:
        lines.extend([
            "## Verdict", "",
            "Aucune règle véritablement nouvelle et fiable n'a été découverte. Les motifs les plus forts sont des macros qui compressent des compositions déjà exprimables par la grammaire. Les zones non analysées sont conservées dans le registre, mais leur support est insuffisant pour proposer une production sans sur-généraliser.", "",
        ])
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
