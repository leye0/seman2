"""POC-08 benchmark over 849 consecutive real partial descriptions."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from research.induction import compare_partial_states
from research.induction.corpus_evidence import load_real_corpus, reference_partial_states

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def run(manifest_path: Path, cache_dir: Path) -> dict:
    raw = manifest_path.read_bytes()
    config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    states = reference_partial_states(graphs)
    deltas = [compare_partial_states(left, right) for left, right in zip(states, states[1:])]
    counts = Counter()
    false_disappearances = 0
    for delta in deltas:
        counts["comparable"] += delta.comparable
        counts["added"] += len(delta.added)
        counts["explicitly_reversed"] += len(delta.explicitly_reversed)
        counts["unchanged"] += len(delta.unchanged)
        counts["unmentioned_after"] += len(delta.unmentioned_after)
        # The representation has no inferred-removal field: unmentioned rows
        # must remain exclusively in the open-world bucket.
        false_disappearances += sum(
            row in {before for before, _ in delta.explicitly_reversed}
            for row in delta.unmentioned_after
        )
    thresholds = config["thresholds"]
    passed = (
        counts["comparable"] == thresholds["required_comparable_pairs"]
        and false_disappearances <= thresholds["maximum_false_disappearances"]
    )
    return {
        "poc": "POC-08",
        "manifest_sha256": sha256(raw).hexdigest(),
        "observation_count": len(graphs),
        "delta_count": len(deltas),
        "counts": dict(counts),
        "false_disappearances": false_disappearances,
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
