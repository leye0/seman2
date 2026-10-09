"""POC-11 controlled transfer benchmark plus real-corpus audit."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from research.induction import ConstructionEvidence, CrossConstructionLearner, EffectTemplate
from research.induction.corpus_evidence import load_real_corpus, reference_transition_episodes
from research.induction.transitions import _observed_effects

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"

ACTIVE = (EffectTemplate("opaque_r", (0, 2), False), EffectTemplate("opaque_r", (1, 2), True))
PASSIVE = (EffectTemplate("opaque_r", (2, 0), False), EffectTemplate("opaque_r", (1, 0), True))
RECEIVE = (EffectTemplate("opaque_r", (2, 1), False), EffectTemplate("opaque_r", (0, 1), True))


def controlled(config):
    rows = []
    specs = (("active", ACTIVE, "active"), ("passive", PASSIVE, "passive"), ("receive", RECEIVE, "recipient-focus"))
    for construction, effects, form in specs:
        for index in range(config["controlled_training_per_construction"]):
            rows.append(ConstructionEvidence.build(f"{construction}-{index}", construction, 3, effects, {"form": form}))
    learner = CrossConstructionLearner(min_support=config["min_support"]).fit(rows)
    correct = predicted = expected_count = residual_ok = 0
    for alignment in learner.alignments:
        arguments = ("held-0", "held-1", "held-2")
        predictions = set(alignment.predict_right(arguments))
        right = next(profile for profile in learner.profiles if profile.construction_id == alignment.right_id)
        expected = {effect.instantiate(arguments) for effect in right.effects}
        correct += len(predictions & expected); predicted += len(predictions); expected_count += len(expected)
        residual_ok += bool(alignment.left_residuals and alignment.right_residuals)
    precision = correct / predicted if predicted else 0.0
    recall = correct / expected_count if expected_count else 0.0
    return {
        "profile_count": len(learner.profiles),
        "alignment_count": len(learner.alignments),
        "precision": precision,
        "recall": recall,
        "residual_preservation": residual_ok / len(learner.alignments) if learner.alignments else 0.0,
        "without_delta_alignment_count": len(CrossConstructionLearner(min_support=4).fit([
            ConstructionEvidence.build(f"empty-{i}", "empty-a" if i < 10 else "empty-b", 3, ()) for i in range(20)
        ]).alignments),
    }


def real_audit(config, cache_dir):
    graphs = load_real_corpus(cache_dir, required=config["real_corpus_observations"])
    all_episodes = reference_transition_episodes(graphs)
    episodes = [row for row in all_episodes if int(row.episode_id.split(":", 1)[0]) < config["real_training_end"]]
    test = [row for row in all_episodes if int(row.episode_id.split(":", 1)[0]) >= 725]
    evidence = []
    for row in episodes:
        effects = _observed_effects(row)
        if not effects:
            continue
        construction = f"{row.event.component_id}|{row.context_id}|{len(row.event.arguments)}"
        evidence.append(ConstructionEvidence.build(row.episode_id, construction, len(row.event.arguments), effects, {"root_rule": row.context_id}))
    learner = CrossConstructionLearner(min_support=config["min_support"]).fit(evidence)
    correct = predicted = gold = matched_episodes = 0
    for alignment in learner.alignments:
        for row in test:
            construction = f"{row.event.component_id}|{row.context_id}|{len(row.event.arguments)}"
            if construction != alignment.right_id:
                continue
            expected = {effect.instantiate(row.event.arguments) for effect in _observed_effects(row)}
            predictions = set(alignment.predict_right(row.event.arguments))
            correct += len(predictions & expected)
            predicted += len(predictions)
            gold += len(expected)
            matched_episodes += 1
    precision = correct / predicted if predicted else 0.0
    recall = correct / gold if gold else 0.0
    return {
        "observation_count": len(graphs),
        "evidence_count": len(evidence),
        "profile_count": len(learner.profiles),
        "alignment_count": len(learner.alignments),
        "heldout_matched_episodes": matched_episodes,
        "heldout_precision": precision,
        "heldout_recall": recall,
    }


def run(path: Path, cache_dir: Path):
    raw = path.read_bytes(); config = json.loads(raw)
    controlled_result = controlled(config); real_result = real_audit(config, cache_dir); thresholds = config["thresholds"]
    passed = controlled_result["precision"] >= thresholds["controlled_precision"] and controlled_result["recall"] >= thresholds["controlled_recall"] and controlled_result["residual_preservation"] >= thresholds["residual_preservation"]
    return {"poc": "POC-11", "manifest_sha256": sha256(raw).hexdigest(), "controlled": controlled_result, "real_audit": real_result, "passed": passed}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--manifest",type=Path,default=DEFAULT_MANIFEST);parser.add_argument("--cache-dir",type=Path,default=DEFAULT_CACHE_DIR);parser.add_argument("--output",type=Path);args=parser.parse_args();payload=json.dumps(run(args.manifest,args.cache_dir),indent=2,sort_keys=True)+"\n"
    if args.output:args.output.write_text(payload,encoding="utf-8")
    else:print(payload,end="")


if __name__ == "__main__":main()
