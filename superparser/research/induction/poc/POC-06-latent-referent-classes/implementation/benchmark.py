"""POC-06 benchmark over all 849 cached real observations."""

from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

from research.induction import LatentReferentModel, SubstitutionObservation
from research.induction.corpus_evidence import load_real_corpus, referent_substitution_observations

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures" / "manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def evaluate(model: LatentReferentModel, rows: list[SubstitutionObservation]) -> dict:
    actual = defaultdict(set)
    for row in rows:
        actual[row.context].add(row.referent_id)
    known = set(model.signatures)
    tp = predicted_count = gold_count = covered = eligible = 0
    for context, referents in actual.items():
        referents &= known
        if not referents:
            continue
        eligible += 1
        prediction = model.predict(context.component_id, context.port_id)
        if prediction.abstained:
            continue
        covered += 1
        predicted = set(prediction.referent_ids)
        tp += len(predicted & referents)
        predicted_count += len(predicted)
        gold_count += len(referents)
    precision = tp / predicted_count if predicted_count else 0.0
    recall = tp / gold_count if gold_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    noun_precision = gold_count / (len(known) * covered) if covered else 0.0
    noun_f1 = 2 * noun_precision / (noun_precision + 1) if noun_precision else 0.0
    return {"eligible_contexts": eligible, "covered_contexts": covered, "precision": precision, "recall": recall, "f1": f1, "noun_baseline_f1": noun_f1}


def run(manifest_path: Path, cache_dir: Path) -> dict:
    raw = manifest_path.read_bytes()
    config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    split = config["splits"]
    train = referent_substitution_observations(graphs[:split["training_end"]])
    validation = referent_substitution_observations(graphs[split["training_end"]:split["validation_end"]], offset=split["training_end"])
    test = referent_substitution_observations(graphs[split["validation_end"]:split["test_end"]], offset=split["validation_end"])
    choices = []
    for similarity in config["context_similarity_grid"]:
        for membership in config["membership_ratio_grid"]:
            model = LatentReferentModel(
                context_similarity=similarity,
                membership_ratio=membership,
                min_contexts=config["min_contexts"],
                min_referents=config["min_referents"],
            ).fit(train)
            score = evaluate(model, validation)
            utility = score["f1"] * score["covered_contexts"] / max(1, score["eligible_contexts"])
            choices.append((utility, score["f1"], score["covered_contexts"], -similarity, -membership, model, score))
    _, _, _, _, _, model, validation_score = max(choices, key=lambda row: row[:5])
    test_score = evaluate(model, test)
    thresholds = config["thresholds"]
    passed = (
        test_score["covered_contexts"] >= thresholds["minimum_test_contexts"]
        and test_score["f1"] >= thresholds["minimum_test_f1"]
        and (not thresholds["must_beat_noun_f1"] or test_score["f1"] > test_score["noun_baseline_f1"])
    )
    return {
        "poc": "POC-06",
        "manifest_sha256": sha256(raw).hexdigest(),
        "observation_count": len(graphs),
        "substitutions": {"training": len(train), "validation": len(validation), "test": len(test)},
        "selected_policy": {"context_similarity": model.context_similarity, "membership_ratio": model.membership_ratio},
        "family_count": len(model.families),
        "validation": validation_score,
        "test": test_score,
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.manifest, args.cache_dir), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
