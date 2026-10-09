"""POC-10 controlled revision benchmark plus 849-observation audit."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from research.induction import HypothesisReviser, RevisionEvidence, TransitionInducer
from research.induction.corpus_evidence import load_real_corpus, reference_transition_episodes
from research.induction.transitions import _evaluate

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def rows(prefix, hypothesis, context, supports, count, reliability=1.0):
    return [
        RevisionEvidence(f"{prefix}-{index}", hypothesis, context, supports, prefix, reliability)
        for index in range(count)
    ]


def controlled(config):
    policy = config["policy"]
    reviser = HypothesisReviser(**policy)
    count = config["controlled"]["initial_support_per_context"]
    initial = rows("old-physical", "h", "physical", True, count) + rows("old-idiom", "h", "idiom", True, count)
    reviser.register("h", {"kind": "opaque-equivalence"}, initial)
    reviser.revise(
        "h",
        rows("new-physical", "h", "physical", False, config["controlled"]["late_counterexamples"])
        + rows("new-idiom", "h", "idiom", True, config["controlled"]["late_confirmations"]),
    )
    active_contexts = {revision.context_id for revision in reviser.active}
    before_errors = config["controlled"]["late_counterexamples"]
    after_errors = 0 if "physical" not in active_contexts else before_errors
    expected_evidence = len(initial) + config["controlled"]["late_counterexamples"] + config["controlled"]["late_confirmations"]
    latest_parent = reviser.latest("h")
    preserved = len(latest_parent.evidence_ids) + len(latest_parent.counterexample_ids) + len(latest_parent.ignored_evidence_ids)
    return {
        "before_errors": before_errors,
        "after_errors": after_errors,
        "error_reduction": (before_errors - after_errors) / before_errors,
        "active_contexts": sorted(context for context in active_contexts if context),
        "parent_status": latest_parent.status,
        "lineage_versions": len(reviser.lineage("h")),
        "lineage_completeness": preserved / expected_evidence,
    }


def real_audit(config, cache_dir):
    graphs = load_real_corpus(cache_dir, required=config["real_corpus_observations"])
    episodes = reference_transition_episodes(graphs)
    number = lambda row: int(row.episode_id.split(":", 1)[0])
    train = [row for row in episodes if number(row) < config["real_training_end"]]
    revision = [row for row in episodes if config["real_training_end"] <= number(row) < config["real_revision_end"]]
    model = TransitionInducer(min_support=3, min_confidence=0.8, min_coverage=0.3, min_lift=1.5).fit(train)
    ledger = HypothesisReviser(**config["policy"])
    created = []
    for hypothesis in model.hypotheses:
        initial = rows("train-support-" + hypothesis.hypothesis_id, hypothesis.hypothesis_id, hypothesis.context_id, True, hypothesis.support)
        initial += rows("train-counter-" + hypothesis.hypothesis_id, hypothesis.hypothesis_id, hypothesis.context_id, False, hypothesis.contradictions)
        ledger.register(hypothesis.hypothesis_id, {"component": hypothesis.component_id, "effect": repr(hypothesis.effect)}, initial)
        applicable = [row for row in revision if row.event.component_id == hypothesis.component_id and row.context_id == hypothesis.context_id]
        support, counter = _evaluate(hypothesis.effect, applicable)
        new = [RevisionEvidence("validation-support-" + row.episode_id, hypothesis.hypothesis_id, hypothesis.context_id, True, row.event.source_id) for row in support]
        new += [RevisionEvidence("validation-counter-" + row.episode_id, hypothesis.hypothesis_id, hypothesis.context_id, False, row.event.source_id) for row in counter]
        created.extend(ledger.revise(hypothesis.hypothesis_id, new))
    return {
        "observation_count": len(graphs),
        "seed_hypotheses": len(model.hypotheses),
        "retired": sum(row.status == "retired" for row in created),
        "specializations": sum(row.specialization_of is not None for row in created),
        "new_support": sum(len(row.evidence_ids) for row in created) - sum(h.support for h in model.hypotheses),
        "new_counterexamples": sum(len(row.counterexample_ids) for row in created),
    }


def run(path: Path, cache_dir: Path):
    raw = path.read_bytes(); config = json.loads(raw)
    controlled_result = controlled(config)
    real_result = real_audit(config, cache_dir)
    thresholds = config["thresholds"]
    passed = controlled_result["error_reduction"] >= thresholds["controlled_error_reduction"] and controlled_result["lineage_completeness"] >= thresholds["lineage_completeness"]
    return {"poc": "POC-10", "manifest_sha256": sha256(raw).hexdigest(), "controlled": controlled_result, "real_audit": real_result, "passed": passed}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST); parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR); parser.add_argument("--output", type=Path); args = parser.parse_args()
    payload = json.dumps(run(args.manifest, args.cache_dir), indent=2, sort_keys=True) + "\n"
    if args.output: args.output.write_text(payload, encoding="utf-8")
    else: print(payload, end="")


if __name__ == "__main__": main()
