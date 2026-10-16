"""Reproducible VerbNet 3.4 coverage + prefix lookup benchmark.

Run from the project root:
  PYTHONPATH=superparser .venv-popper/bin/python superparser/scripts/benchmark_verbnet_lr.py --fetch
Or pass --verbnet-dir to avoid network access. Standard library only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import statistics
import tempfile
from time import perf_counter_ns
import tracemalloc
from urllib.request import Request, urlopen
from zipfile import ZipFile

from research.verbnet_lr import PrefixIndex, compile_directory, write_index, read_index

ROOT = Path(__file__).resolve().parents[1]
PIN = "ae8e9cfdc2c0d3414b748763612f1a0a34194cc1"
ARCHIVE_URL = "https://github.com/cu-clear/verbnet/archive/" + PIN + ".zip"


def wordnet_index(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        if path.is_dir():
            path /= "index.sense"
        if not path.is_file():
            raise FileNotFoundError(f"WordNet index.sense not found: {path}")
        return path
    source = ROOT / "data" / "wordnet_path"
    if source.is_file():
        directory = Path(source.read_text(encoding="utf-8").strip())
        candidate = directory / "index.sense"
        if candidate.is_file():
            return candidate
    return None


@contextmanager
def xml_source(directory: str | None, fetch: bool):
    if directory:
        path = Path(directory)
        if not path.is_dir():
            raise NotADirectoryError(path)
        yield path
        return
    if not fetch:
        raise ValueError("Provide --verbnet-dir or --fetch")
    req = Request(ARCHIVE_URL, headers={"User-Agent": "Seman2-VerbNet-research"})
    with urlopen(req, timeout=90) as response:
        data = response.read()
    with tempfile.TemporaryDirectory(prefix="seman2-verbnet-") as tmp:
        dest = Path(tmp)
        with ZipFile(BytesIO(data)) as archive:
            for member in archive.infolist():
                parts = member.filename.split("/")
                if len(parts) != 3 or parts[1] != "verbnet3.4" or not parts[2].endswith(".xml"):
                    continue
                if member.file_size > 2_000_000:
                    raise ValueError(f"unexpectedly large XML file: {member.filename}")
                # Flat basename extraction: cannot traverse out of tempdir.
                (dest / Path(parts[2]).name).write_bytes(archive.read(member))
        if not any(dest.glob("*.xml")):
            raise ValueError("VerbNet archive contained no VerbNet 3.4 XML files")
        yield dest


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * q))], 4)


def syntax_validation_coverage(index: PrefixIndex, path: Path) -> dict:
    """Counts verb lemmas in Seman2's validation cases; NOT grammar accuracy."""
    out = {"total": 0, "predicate_present": 0, "predicate_in_verbnet": 0,
           "by_split": {}, "missing_predicates": []}
    if not path.exists():
        out["error"] = f"missing {path}"
        return out
    splits = {}
    missing = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        split = case.get("split", "unspecified")
        d = splits.setdefault(split, {"total": 0, "predicate_present": 0, "predicate_in_verbnet": 0})
        d["total"] += 1
        out["total"] += 1
        lemma = case.get("predicate")
        if not lemma:
            continue
        d["predicate_present"] += 1
        out["predicate_present"] += 1
        if str(lemma).casefold() in index._frames:
            d["predicate_in_verbnet"] += 1
            out["predicate_in_verbnet"] += 1
        else:
            missing[str(lemma).casefold()] += 1
    out["by_split"] = splits
    out["missing_predicates"] = sorted(missing.items(), key=lambda x: (-x[1], x[0]))
    return out


def oracle_examples(index: PrefixIndex, path: Path) -> dict:
    """Explicitly annotated event sequences; no claim of end-to-end parsing."""
    stats = Counter()
    observations = []
    if not path.exists():
        return {"error": f"missing {path}"}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        case = json.loads(raw)
        events = tuple(case["events"])
        p = index.predict(case["lemma"], events)
        stats["cases"] += 1
        kind = case["expected"]
        stats["positive" if kind == "attested" else "contrast"] += 1
        if p.status == "ATTESTED":
            stats["attested_" + kind] += 1
        if p.status == "UNKNOWN":
            stats["unknown_" + kind] += 1
        observations.append({"id": case["id"], "text": case["text"], "oracle_events": list(events),
                             "expected": kind, "predicted": p.status,
                             "matching_frames": len(p.matching_frames)})
    return {"totals": dict(stats), "observations": observations,
            "warning": "Manual event annotations, not parse outputs; contrast UNKNOWN does not imply ungrammaticality."}


def benchmark(index: PrefixIndex, frames: tuple, iterations: int) -> dict:
    # Fixed deterministic workload, independent of host timing.
    cases = []
    for frame in frames:
        if frame.symbols and len(frame.symbols) <= 6 and len(cases) < 250:
            prefix = tuple(alts[0] for alts in frame.symbols[:-1])
            cases.append((frame.lemma, prefix))
    if not cases:
        return {"error": "no compiled frames"}
    for lemma, events in cases:
        index.predict(lemma, events)  # warm lazy trie
    timing_us = []
    start = perf_counter_ns()
    for i in range(iterations):
        lemma, events = cases[i % len(cases)]
        t = perf_counter_ns()
        index.predict(lemma, events)
        timing_us.append((perf_counter_ns() - t) / 1_000)
    elapsed = (perf_counter_ns() - start) / 1e9
    return {"calls": iterations, "distinct_cases": len(cases),
            "rate_calls_per_sec": round(iterations / elapsed, 2) if elapsed else None,
            "median_us": percentile(timing_us, .5), "p95_us": percentile(timing_us, .95),
            "p99_us": percentile(timing_us, .99), "max_us": round(max(timing_us), 4),
            "note": "Isolated warmed index.lookup; excludes recognition, morphology and full parsing."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--verbnet-dir", help="local verbnet3.4 XML directory")
    src.add_argument("--fetch", action="store_true", help="download pinned upstream VerbNet snapshot")
    p.add_argument("--wordnet-sense-index", help="WordNet index.sense or dict directory")
    p.add_argument("--cases", default=str(ROOT / "research" / "verbnet_lr" / "oracle_cases.jsonl"))
    p.add_argument("--validation", default=str(ROOT / "data" / "syntax_correctness_validation.jsonl"))
    p.add_argument("--iterations", type=int, default=20000)
    p.add_argument("--report", default=str(ROOT / "research" / "verbnet_lr" / "latest_report.json"))
    p.add_argument("--index-out", help="write compiled index for later usage")
    args = p.parse_args(argv)
    if args.iterations < 100:
        p.error("--iterations must be >= 100")
    sense = wordnet_index(args.wordnet_sense_index)
    with xml_source(args.verbnet_dir, args.fetch) as source:
        tracemalloc.start()
        start_ns = perf_counter_ns()
        frames, stats = compile_directory(source, sense)
        compile_ms = (perf_counter_ns() - start_ns) / 1e6
        index = PrefixIndex(frames)
        lookup_benchmark = benchmark(index, frames, args.iterations)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if args.index_out:
            write_index(args.index_out, frames, stats)
            verify = read_index(args.index_out)
            if verify.lemmas() != index.lemmas():
                raise RuntimeError("roundtrip index mismatch")
        result = {
            "schema": 1, "source": {"verbnet_repo": "cu-clear/verbnet", "revision": PIN if args.fetch else "local-unverified",
              "wordnet_sense_index": str(sense) if sense else None,
              "sense_alignment_enabled": sense is not None},
            "compilation": {**stats, "duration_ms": round(compile_ms, 3),
                            "peak_compilation_plus_benchmark_memory_mb": round(peak / 1048576, 3),
                            "frames_with_exact_link": sum(f.link == "exact" for f in frames),
                            "frames_lemma_only": sum(f.link == "lemma_only" for f in frames),
                            "frames_unresolved": sum(f.link == "unresolved" for f in frames)},
            "coverage_on_seman2_validation": syntax_validation_coverage(index, Path(args.validation)),
            "manual_event_cases": oracle_examples(index, Path(args.cases)),
            "lookup_benchmark": lookup_benchmark,
            "limitations": ["No full Seman2 parser invocation", "No estimated precision/recall of grammaticality",
                            "VerbNet is incomplete; UNKNOWN is not rejection",
                            "Memory includes warmed tries and temporary allocations",
                            "The oracle examples are manually annotated, not automatically parsed"]
        }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": args.report, "xml_files": result["compilation"]["xml_files"],
                      "compiled_frames": len(frames),
                      "coverage": result["coverage_on_seman2_validation"]["predicate_in_verbnet"],
                      "median_lookup_us": lookup_benchmark.get("median_us")}, indent=2))


if __name__ == "__main__":
    main()
