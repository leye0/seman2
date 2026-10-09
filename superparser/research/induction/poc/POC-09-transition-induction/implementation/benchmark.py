"""POC-09 benchmark over event/delta episodes from all 849 observations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from research.induction import TransitionInducer
from research.induction.corpus_evidence import load_real_corpus, reference_transition_episodes
from research.induction.transitions import _observed_effects

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def episode_number(episode) -> int:
    return int(episode.episode_id.split(":", 1)[0])


def baseline_table(episodes, key, min_support, min_coverage):
    groups, counts = defaultdict(list), defaultdict(Counter)
    for episode in episodes:
        groups[key(episode)].append(episode)
        counts[key(episode)].update(_observed_effects(episode))
    return {
        group: {
            effect for effect, count in rows.items()
            if count >= min_support and count / len(groups[group]) >= min_coverage
        }
        for group, rows in counts.items()
    }


def evaluate(episodes, predictor):
    true_positive = predicted_count = gold_count = 0
    for episode in episodes:
        expected = {effect.instantiate(episode.event.arguments) for effect in _observed_effects(episode)}
        predicted = predictor(episode)
        true_positive += sum(row in expected for row in predicted)
        predicted_count += len(predicted)
        gold_count += len(expected)
    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / gold_count if gold_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"predictions": predicted_count, "correct": true_positive, "precision": precision, "recall": recall, "f1": f1}


def instantiate(effects, episode):
    rows = []
    for effect in effects:
        try:
            rows.append(effect.instantiate(episode.event.arguments))
        except ValueError:
            pass
    return rows


def run(manifest_path: Path, cache_dir: Path) -> dict:
    raw = manifest_path.read_bytes()
    config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    episodes = reference_transition_episodes(graphs)
    train = [row for row in episodes if episode_number(row) < config["training_end"]]
    test = [row for row in episodes if episode_number(row) >= config["test_start"]]
    model = TransitionInducer(**config["policy"]).fit(train)
    learned = evaluate(
        test,
        lambda episode: [row.proposition for row in model.predict(episode.event, episode.context_id)],
    )
    syntax = baseline_table(
        train,
        lambda episode: episode.context_id,
        config["policy"]["min_support"],
        config["policy"]["min_coverage"],
    )
    frequency = baseline_table(
        train,
        lambda episode: "*",
        config["policy"]["min_support"],
        config["policy"]["min_coverage"],
    )
    syntax_score = evaluate(test, lambda episode: instantiate(syntax.get(episode.context_id, ()), episode))
    frequency_score = evaluate(test, lambda episode: instantiate(frequency.get("*", ()), episode))
    thresholds = config["thresholds"]
    passed = (
        learned["precision"] >= thresholds["minimum_precision"]
        and (not thresholds["must_beat_frequency_f1"] or learned["f1"] > frequency_score["f1"])
        and (not thresholds["must_beat_syntax_f1"] or learned["f1"] > syntax_score["f1"])
    )
    return {
        "poc": "POC-09",
        "manifest_sha256": sha256(raw).hexdigest(),
        "observation_count": len(graphs),
        "episodes": {"all": len(episodes), "training": len(train), "test": len(test)},
        "hypothesis_count": len(model.hypotheses),
        "learned": learned,
        "frequency_baseline": frequency_score,
        "syntax_baseline": syntax_score,
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
