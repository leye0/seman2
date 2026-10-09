"""POC-12 benchmark over shuffled streams of all 849 observations."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import time

from research.induction import IncrementalStructuralIndex, batch_signature_groups
from research.induction.corpus_evidence import load_real_corpus

POC_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = POC_DIR / "fixtures/manifest.json"
ROOT = Path(__file__).resolve().parents[6]
DEFAULT_CACHE_DIR = ROOT / ".local/cache/seman2/induction"


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def ingest(graphs, min_support):
    index = IncrementalStructuralIndex(min_support=min_support)
    latencies = []
    comparisons = 0
    for graph in graphs:
        started = time.perf_counter_ns()
        result = index.ingest(graph)
        latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        comparisons += result.comparisons
    return index, latencies, comparisons


def run(path: Path, cache_dir: Path):
    raw = path.read_bytes(); config = json.loads(raw)
    graphs = load_real_corpus(cache_dir, required=config["required_observations"])
    batch = batch_signature_groups(graphs, min_support=config["min_support"])
    runs = []
    component_sets = []
    for seed in config["seeds"]:
        stream = list(graphs); random.Random(seed).shuffle(stream)
        index, latencies, comparisons = ingest(stream, config["min_support"])
        found = {row.signature: row.member_ids for row in index.active_components}
        component_sets.append(set(found))
        runs.append({
            "seed": seed,
            "component_count": len(found),
            "batch_equal": found == batch,
            "comparisons": comparisons,
            "p50_ms": percentile(latencies, 0.50),
            "p95_ms": percentile(latencies, 0.95),
            "p99_ms": percentile(latencies, 0.99),
            "snapshot_bytes": len(json.dumps(index.as_dict(), sort_keys=True).encode()),
        })
    scaling = []
    for size in config["prefixes"]:
        _, latencies, comparisons = ingest(graphs[:size], config["min_support"])
        scaling.append({"observations": size, "comparisons": comparisons, "mean_ms": sum(latencies) / len(latencies)})
    all_pairs = len(graphs) * (len(graphs) - 1) // 2
    maximum_fraction = max(run["comparisons"] / all_pairs for run in runs)
    component_delta = max(len(rows) for rows in component_sets) - min(len(rows) for rows in component_sets)
    thresholds = config["thresholds"]
    passed = (
        all(run["batch_equal"] for run in runs)
        and component_delta <= thresholds["maximum_order_component_delta"]
        and maximum_fraction <= thresholds["maximum_comparison_fraction"]
    )
    return {
        "poc": "POC-12",
        "manifest_sha256": sha256(raw).hexdigest(),
        "observation_count": len(graphs),
        "batch_component_count": len(batch),
        "runs": runs,
        "scaling": scaling,
        "maximum_comparison_fraction": maximum_fraction,
        "passed": passed,
    }


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--manifest",type=Path,default=DEFAULT_MANIFEST);parser.add_argument("--cache-dir",type=Path,default=DEFAULT_CACHE_DIR);parser.add_argument("--output",type=Path);args=parser.parse_args();payload=json.dumps(run(args.manifest,args.cache_dir),indent=2,sort_keys=True)+"\n"
    if args.output:args.output.write_text(payload,encoding="utf-8")
    else:print(payload,end="")


if __name__ == "__main__":main()
