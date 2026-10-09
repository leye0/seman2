"""Transparent temporary controlled benchmark for POC-09."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from research.induction import (
    EventOccurrence,
    PartialState,
    ReportedProposition,
    TransitionEpisode,
    TransitionInducer,
)

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/controlled_manifest.json"


def proposition(relation, *arguments, truth=True):
    return ReportedProposition(relation, tuple(arguments), truth)


def episode(index, component, outcome, templates):
    a, b, obj = f"person_{index}_a", f"person_{index}_b", f"item_{index}"
    before = PartialState.build(f"before-{index}", "controlled", 0, [proposition("opaque_r1", a, obj)])
    if outcome == "positive":
        after_rows = [proposition("opaque_r1", a, obj, truth=False), proposition("opaque_r1", b, obj)]
    elif outcome == "counterexample":
        after_rows = [proposition("opaque_r1", a, obj), proposition("opaque_r1", b, obj, truth=False)]
    else:
        after_rows = [proposition("opaque_r1", a, obj)]
    after = PartialState.build(f"after-{index}", "controlled", 2, after_rows)
    event = EventOccurrence(f"event-{index}", component, (a, b, obj), "controlled", 1)
    row = TransitionEpisode(f"episode-{index}", "controlled-context", before, event, after)
    sentences = {
        "before": templates["before"].format(a=a, b=b, object=obj),
        "event": (templates["event"] if component == "opaque_event_a" else templates["control"]).format(a=a, b=b, object=obj),
        "after": templates["after"].format(a=a, b=b, object=obj),
    }
    return row, sentences


def f1(predicted, expected):
    overlap = len(predicted & expected)
    precision = overlap / len(predicted) if predicted else 0.0
    recall = overlap / len(expected) if expected else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def run(path: Path) -> dict:
    raw = path.read_bytes()
    config = json.loads(raw)
    templates = config["sentence_templates"]
    rows, surfaces, cursor = [], [], 0
    for outcome, component, count in (
        ("positive", "opaque_event_a", config["positive_training"]),
        ("counterexample", "opaque_event_a", config["counterexamples"]),
        ("neutral", "opaque_event_b", config["control_training"]),
    ):
        for _ in range(count):
            row, text = episode(cursor, component, outcome, templates)
            rows.append(row); surfaces.append(text); cursor += 1
    model = TransitionInducer(**config["policy"]).fit(rows)
    scores = []
    explanation_count = 0
    for _ in range(config["heldout"]):
        row, _ = episode(cursor, "opaque_event_a", "positive", templates); cursor += 1
        predictions = model.predict(row.event, row.context_id)
        predicted = {prediction.proposition for prediction in predictions}
        a, b, obj = row.event.arguments
        expected = {proposition("opaque_r1", a, obj, truth=False), proposition("opaque_r1", b, obj)}
        scores.append(f1(predicted, expected))
        explanation_count += bool(predictions) and all(prediction.explanation_chain for prediction in predictions)
    controls = [episode(cursor + index, "opaque_event_b", "neutral", templates)[0] for index in range(config["heldout"])]
    abstention = sum(not model.predict(row.event, row.context_id) for row in controls) / len(controls)
    heldout_f1 = sum(scores) / len(scores)
    passed = heldout_f1 >= config["thresholds"]["minimum_heldout_f1"] and abstention >= config["thresholds"]["minimum_control_abstention"]
    return {
        "poc": "POC-09-controlled",
        "manifest_sha256": sha256(raw).hexdigest(),
        "temporary_controlled_data": True,
        "training_sequences": len(rows),
        "surface_example": surfaces[0],
        "hypothesis_count": len(model.hypotheses),
        "heldout_f1": heldout_f1,
        "control_abstention": abstention,
        "explanation_rate": explanation_count / len(scores),
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.manifest), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
