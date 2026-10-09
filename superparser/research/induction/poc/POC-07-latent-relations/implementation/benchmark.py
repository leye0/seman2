"""POC-07 benchmark over reference constraints in all 849 observations."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from research.induction import LatentRelationModel
from research.induction.corpus_evidence import load_real_corpus, reference_relation_observations

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def run(manifest_path: Path, cache_dir: Path) -> dict:
    raw = manifest_path.read_bytes()
    config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    train = reference_relation_observations(graphs[: config["training_end"]])
    test = reference_relation_observations(graphs[config["test_start"] :], offset=config["test_start"])
    model = LatentRelationModel(**config["policy"]).fit(train)
    observed = {
        (row.scenario_id, row.domain_id, row.source_id, row.target_id, row.relation_id): row.truth
        for row in test
    }
    predictions = {}
    for row in test:
        if not row.truth:
            continue
        for prediction in model.predict(row):
            key = (
                prediction.scenario_id,
                prediction.domain_id,
                prediction.source_id,
                prediction.target_id,
                prediction.relation_id,
                prediction.truth,
            )
            predictions[key] = prediction
    correct = sum(observed.get(key[:5]) == key[5] for key in predictions)
    precision = correct / len(predictions) if predictions else 0.0
    thresholds = config["thresholds"]
    passed = (
        len(predictions) >= thresholds["minimum_test_predictions"]
        and precision >= thresholds["minimum_test_precision"]
    )
    return {
        "poc": "POC-07",
        "manifest_sha256": sha256(raw).hexdigest(),
        "observation_count": len(graphs),
        "explicit_constraints": {"training": len(train), "test": len(test)},
        "hypotheses": [hypothesis.as_dict() for hypothesis in model.hypotheses],
        "test_prediction_count": len(predictions),
        "test_correct": correct,
        "test_precision": precision,
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
