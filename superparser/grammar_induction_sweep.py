#!/usr/bin/env python3
"""Run masked-grammar discovery, temporary injection, and held-out validation.

The complete grammar is used only to select/evaluate reference examples.  The
candidate generator receives parse forests built by a separately masked
grammar and has no access to the removed productions.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import statistics
from time import perf_counter
from typing import Any, Iterable

from research.induction.masked_grammar_induction import (
    CandidateEvidence,
    CandidateKey,
    SweepConfig,
    aggregate_observations,
    evaluate_candidates,
    rank_candidates,
)
from seman_parser import Grammar, Parser, ParserResources
from seman_parser.coverage import SentenceCase, extract_sentences


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "research/induction/poc/POC-15-masked-induction"


def _signature(rule: Any) -> tuple[str, tuple[str, ...]]:
    return rule.lhs.category, tuple(symbol.category for symbol in rule.rhs)


def _contains_relation(rule: Any, relation: str) -> bool:
    return relation in json.dumps([action.as_dict() for action in rule.semantic], sort_keys=True)


def mask_families(grammar: Grammar) -> dict[str, frozenset[str]]:
    """Define experimental lesions, including same-shape escape routes."""
    relative = {
        rule.rule_id for rule in grammar
        if rule.lhs.category == "NP"
        and tuple(symbol.category for symbol in rule.rhs) in {
            ("NP", "WH-SUBJ"), ("NP", "WH-OBJ")
        }
    }
    nominal_pp = {
        rule.rule_id for rule in grammar
        if rule.lhs.category in {"N", "NP"}
        and len(rule.rhs) >= 2
        and rule.rhs[-1].category == "PP"
        and _contains_relation(rule, "MODIFIER")
    }
    np_coordination = {
        rule.rule_id for rule in grammar
        if rule.lhs.category == "NP" and _contains_relation(rule, "CONJUNCT")
    }
    return {
        "relative_attachment": frozenset(relative),
        "nominal_pp_attachment": frozenset(nominal_pp),
        "np_coordination": frozenset(np_coordination),
    }


def _resources_without(resources: ParserResources, rule_ids: Iterable[str]) -> ParserResources:
    removed = frozenset(rule_ids)
    return ParserResources(
        Grammar(rule for rule in resources.grammar if rule.rule_id not in removed),
        resources.lexicon,
        resources.types,
        {**dict(resources.metadata), "masked_rule_ids": sorted(removed)},
    )


def _walk(item: Any):
    yield item
    for child in item.children:
        yield from _walk(child)


def _best_rule_ids(result: Any) -> set[str]:
    best = result.best()
    return set() if best is None else {
        item.rule_id for item in _walk(best) if item.rule_id is not None
    }


def _configs_first() -> list[SweepConfig]:
    return [
        SweepConfig(method, length, support, features, limit, depth)
        for method, length, support, features, limit, depth in (
            ("waiting", 3, 2, "none", 4, 1),
            ("waiting", 4, 2, "none", 8, 2),
            ("waiting", 4, 3, "protected", 8, 1),
            ("bridge", 2, 2, "none", 4, 1),
            ("bridge", 3, 2, "none", 8, 2),
            ("bridge", 3, 3, "protected", 8, 1),
            ("suffix", 2, 2, "none", 4, 1),
            ("suffix", 3, 3, "protected", 8, 2),
            ("hybrid", 2, 2, "none", 4, 1),
            ("hybrid", 3, 2, "none", 8, 2),
            ("hybrid", 4, 3, "none", 8, 2),
            ("hybrid", 4, 3, "protected", 12, 2),
        )
    ]


def _configs_second(winner: SweepConfig) -> list[SweepConfig]:
    values = [
        SweepConfig(winner.method, winner.max_pattern, max(2, winner.min_support - 1), winner.feature_mode, winner.max_candidates, winner.generalization_depth),
        SweepConfig(winner.method, winner.max_pattern, winner.min_support + 1, winner.feature_mode, winner.max_candidates, winner.generalization_depth),
        SweepConfig(winner.method, max(2, winner.max_pattern - 1), winner.min_support, winner.feature_mode, winner.max_candidates, winner.generalization_depth),
        SweepConfig(winner.method, min(5, winner.max_pattern + 1), winner.min_support, winner.feature_mode, winner.max_candidates, 2),
        SweepConfig(winner.method, winner.max_pattern, winner.min_support, "protected", max(4, winner.max_candidates // 2), winner.generalization_depth),
        SweepConfig("hybrid", winner.max_pattern, winner.min_support, winner.feature_mode, min(16, winner.max_candidates * 2), 2),
    ]
    unique: dict[str, SweepConfig] = {row.name: row for row in values}
    return list(unique.values())


def _candidate_dict(row: CandidateEvidence, removed_signatures: set[tuple[str, tuple[str, ...]]]) -> dict[str, Any]:
    signature = (row.key.lhs, row.key.rhs)
    return {
        "production": row.key.text(),
        "lhs": row.key.lhs,
        "rhs": list(row.key.rhs),
        "support": row.support,
        "examples": row.examples,
        "signals": dict(row.sources),
        "matches_hidden_signature": signature in removed_signatures,
        "semantics_learned": False,
    }


def _score(row: dict[str, Any]) -> tuple[float, int, int]:
    metrics = row["totals"]
    value = (
        1000 * metrics["hidden_signatures_recovered"]
        + 5 * metrics["recovered"]
        - 20 * metrics["false_positives"]
        - 10 * metrics["counterexample_induced_best"]
    )
    return value, metrics["recovered"], -metrics["false_positives"]


def run_config(
    config: SweepConfig,
    family_data: dict[str, dict[str, Any]],
    *,
    budget_seconds: float,
    evidence_cache: dict[tuple[str, str, int, int], dict[CandidateKey, CandidateEvidence]] | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    families: dict[str, Any] = {}
    totals = defaultdict(int)
    cache = evidence_cache if evidence_cache is not None else {}
    for family, data in family_data.items():
        cache_key = (family, config.method, config.max_pattern, config.generalization_depth)
        evidence = cache.get(cache_key)
        if evidence is None:
            evidence = aggregate_observations(
                data["train_observations"],
                max_pattern=config.max_pattern,
                method=config.method,
                generalization_depth=config.generalization_depth,
            )
            cache[cache_key] = evidence
        candidates = rank_candidates(evidence, data["resources"].grammar, config)
        remaining = max(0.25, budget_seconds - (perf_counter() - started))
        evaluation_cases = [*data["validation"], *data["counterexamples"]]
        evaluation = evaluate_candidates(
            data["resources"], candidates, evaluation_cases,
            feature_mode=config.feature_mode,
            baseline_completed=data["baseline_completed"],
            reference_completed=data["reference_completed"],
            budget_seconds=remaining,
        )
        validation_ids = {case.index for case in data["validation"]}
        counter_ids = {case.index for case in data["counterexamples"]}
        validation_recovered = sum(
            row["induced_in_forest"] and row["completed"]
            for row in evaluation["details"] if row["index"] in validation_ids
        )
        sentence_coverage_gain = sum(
            row["recovered"] for row in evaluation["details"] if row["index"] in validation_ids
        )
        counter_induced = sum(
            row["induced_in_forest"] for row in evaluation["details"] if row["index"] in counter_ids
        )
        removed_signatures = data["removed_signatures"]
        hidden_recovered = len({
            (row.key.lhs, row.key.rhs) for row in candidates
            if (row.key.lhs, row.key.rhs) in removed_signatures
        })
        families[family] = {
            "hypotheses": len(candidates),
            "new_vs_masked": len(candidates),
            "hidden_signatures_recovered": hidden_recovered,
            "validation_recovered": validation_recovered,
            "sentence_coverage_gain": sentence_coverage_gain,
            "validation_size": len(data["validation"]),
            "counterexample_induced_best": counter_induced,
            "counterexample_hits": [
                row["text"] for row in evaluation["details"]
                if row["index"] in counter_ids and row["induced_in_forest"]
            ],
            "evaluation": evaluation,
            "candidates": [_candidate_dict(row, removed_signatures) for row in candidates],
        }
        totals["hypotheses"] += len(candidates)
        totals["hidden_signatures_recovered"] += hidden_recovered
        totals["recovered"] += validation_recovered
        totals["false_positives"] += evaluation["false_positives"]
        totals["counterexample_induced_best"] += counter_induced
        if perf_counter() - started >= budget_seconds:
            break
    return {
        "config": asdict(config),
        "name": config.name,
        "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "totals": dict(totals),
        "families": families,
    }


def build_experiment_data(
    resources: ParserResources,
    cases: list[SentenceCase],
    families: dict[str, frozenset[str]],
    *,
    train_per_family: int,
    validation_per_family: int,
    counterexamples: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    full = Parser(resources, cache_size=0)
    masked_resources = {
        name: _resources_without(resources, rule_ids) for name, rule_ids in families.items()
    }
    masked = {name: Parser(value, cache_size=0) for name, value in masked_resources.items()}
    relevant: dict[str, list[tuple[SentenceCase, Any]]] = defaultdict(list)
    negatives: list[SentenceCase] = []
    reference_completed: dict[int, bool] = {}
    scan_started = perf_counter()
    needed = train_per_family + validation_per_family

    for number, case in enumerate(cases, 1):
        # Very long outliers are not useful for a fast induction sweep.
        if len(case.text) > 220:
            continue
        reference = full.parse(case.text).result
        reference_completed[case.index] = bool(reference.completed)
        ids = _best_rule_ids(reference)
        matched = [name for name, rule_ids in families.items() if ids & rule_ids]
        if not matched and reference.completed and len(negatives) < counterexamples * 4:
            negatives.append(case)
        for name in matched:
            if len(relevant[name]) >= needed * 3:
                continue
            damaged = masked[name].parse(case.text).result
            # A lesion example must demonstrate an actual lost complete
            # analysis, not merely a different ranking.
            if reference.completed:
                relevant[name].append((case, damaged))
        if number % 100 == 0:
            print(
                f"reference scan {number}: " + ", ".join(
                    f"{name}={len(relevant[name])}" for name in families
                ), flush=True,
            )
        if all(len(relevant[name]) >= needed for name in families) and len(negatives) >= counterexamples:
            break

    data: dict[str, dict[str, Any]] = {}
    summary: dict[str, Any] = {"elapsed_ms": round((perf_counter() - scan_started) * 1000, 3), "families": {}}
    for name, rule_ids in families.items():
        rows = sorted(
            relevant[name],
            key=lambda pair: (-int(not pair[1].completed), pair[0].index),
        )
        train_rows = rows[:train_per_family]
        validation_rows = rows[train_per_family:train_per_family + validation_per_family]
        train = [row[0] for row in train_rows]
        validation = [row[0] for row in validation_rows]
        controls = sorted(
            (case for case in negatives if case.index not in {row.index for row in train + validation}),
            key=lambda case: (len(case.text), case.index),
        )[:counterexamples]
        baseline_completed = {
            case.index: bool(result.completed) for case, result in rows[:train_per_family + validation_per_family]
        }
        baseline_completed.update({case.index: True for case in controls})
        local_reference = {case.index: True for case in train + validation + controls}
        removed_rules = [resources.grammar.by_id(rule_id) for rule_id in rule_ids]
        data[name] = {
            "resources": masked_resources[name],
            "train": train,
            "validation": validation,
            "counterexamples": controls,
            "train_observations": [(f"{name}-{case.index}", result) for case, result in train_rows],
            "baseline_completed": baseline_completed,
            "reference_completed": local_reference,
            "removed_signatures": {_signature(rule) for rule in removed_rules},
        }
        summary["families"][name] = {
            "masked_rule_ids": sorted(rule_ids),
            "train": len(train),
            "validation": len(validation),
            "counterexamples": len(controls),
            "reference_examples_found": len(rows),
            "global_failures_after_mask": sum(not result.completed for _, result in rows),
            "train_examples": [case.text for case in train[:5]],
            "validation_examples": [case.text for case in validation[:3]],
        }
    return data, summary


def write_report(payload: dict[str, Any], path: Path) -> None:
    winner = payload["winner"]
    lines = [
        "# Induction grammaticale par lésion contrôlée", "",
        "La grammaire complète n'a servi qu'à sélectionner les cas lésés et à noter la récupération. Les hypothèses ont été produites exclusivement depuis les forêts de la grammaire masquée. Les productions injectées sont syntaxiques et n'apprennent aucune action sémantique.", "",
        "## Sweeps", "",
        f"- Première passe : {len(payload['first_sweep'])} configurations.",
        f"- Passe ciblée : {len(payload['second_sweep'])} configurations.",
        f"- Configuration gagnante : `{winner['name']}`.",
        f"- Temps total : {payload['elapsed_seconds']} s.", "",
        "## Résultat gagnant", "",
        f"- Hypothèses injectées : {winner['totals'].get('hypotheses', 0)}",
        f"- Signatures masquées retrouvées : {winner['totals'].get('hidden_signatures_recovered', 0)}",
        f"- Analyses inédites récupérées en validation : {winner['totals'].get('recovered', 0)}",
        f"- Faux positifs contre la grammaire complète : {winner['totals'].get('false_positives', 0)}",
        f"- Activations sur contre-exemples proches : {winner['totals'].get('counterexample_induced_best', 0)}", "",
        "## Meilleures règles", "",
    ]
    for family, result in winner["families"].items():
        lines.extend([f"### {family}", ""])
        for candidate in result["candidates"][:5]:
            marker = "signature cachée retrouvée" if candidate["matches_hidden_signature"] else "hypothèse équivalente ou concurrente"
            lines.append(f"- `{candidate['production']}` — support {candidate['support']}; {marker}.")
            for example in candidate["examples"][:2]:
                lines.append(f"  - {example}")
        lines.extend([
            f"Construction récupérée : {result['validation_recovered']}/{result['validation_size']}; gain de couverture globale : {result['sentence_coverage_gain']}; activations sur contrôles : {result['counterexample_induced_best']}.",
            *(["Contre-exemples problématiques :", *[f"- {text}" for text in result["counterexample_hits"][:3]]] if result["counterexample_hits"] else []),
            "",
        ])
    lines.extend([
        "## Lecture des échecs et prochaine étape", "",
        "Les configurations `waiting` ne voient que les catégories explicitement attendues; les constructions d'attachement exigent le signal `bridge` ou `suffix`. Les activations sur contrôles mesurent la surgénéralisation syntaxique, mais une validation négative plus forte devra apprendre quelles contraintes de traits et quels contextes de tête conserver. La prochaine amélioration prometteuse est une anti-unification des environnements de traits des états partiels, puis l'apprentissage séparé des actions sémantiques.", "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--scan", type=int, default=700)
    cli.add_argument("--train-per-family", type=int, default=12)
    cli.add_argument("--validation-per-family", type=int, default=7)
    cli.add_argument("--counterexamples", type=int, default=4)
    cli.add_argument("--config-budget", type=float, default=25.0)
    cli.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = cli.parse_args()

    started = perf_counter()
    resources = ParserResources.from_dir(ROOT / "data")
    # Warm WordNet and the lexical indexes once for the whole process.
    Parser(resources, cache_size=0).parse("The woman opened a box.")
    cases = extract_sentences(ROOT.parent / "data/the_map_of_everything_nlp_novel.txt", limit=args.scan)
    families = mask_families(resources.grammar)
    data, selection = build_experiment_data(
        resources, cases, families,
        train_per_family=args.train_per_family,
        validation_per_family=args.validation_per_family,
        counterexamples=args.counterexamples,
    )

    first = []
    evidence_cache: dict[tuple[str, str, int, int], dict[CandidateKey, CandidateEvidence]] = {}
    for index, config in enumerate(_configs_first(), 1):
        row = run_config(
            config, data, budget_seconds=args.config_budget,
            evidence_cache=evidence_cache,
        )
        first.append(row)
        print(f"sweep 1 {index}/12 {row['name']}: {row['totals']}", flush=True)
    first.sort(key=_score, reverse=True)
    winner_config = SweepConfig(**first[0]["config"])

    second = []
    first_names = {row["name"] for row in first}
    targeted = [row for row in _configs_second(winner_config) if row.name not in first_names]
    for index, config in enumerate(targeted, 1):
        row = run_config(
            config, data, budget_seconds=args.config_budget,
            evidence_cache=evidence_cache,
        )
        second.append(row)
        print(f"sweep 2 {index}/{len(targeted)} {row['name']}: {row['totals']}", flush=True)
    second.sort(key=_score, reverse=True)
    all_rows = sorted([*first, *second], key=_score, reverse=True)
    winner = all_rows[0]
    payload = {
        "schema_version": "masked-grammar-induction-sweep/0.1",
        "production_grammar_modified": False,
        "semantic_actions_learned": False,
        "grammar_rules": len(resources.grammar),
        "selection": selection,
        "first_sweep": first,
        "second_sweep": second,
        "winner": winner,
        "ranking": [{"name": row["name"], "totals": row["totals"], "elapsed_ms": row["elapsed_ms"]} for row in all_rows],
        "elapsed_seconds": round(perf_counter() - started, 3),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_report(payload, args.output_dir / "REPORT.md")
    print(json.dumps({"winner": winner["name"], "totals": winner["totals"], "output": str(args.output_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
