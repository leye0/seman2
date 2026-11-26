"""Native ERG/ACE diagnostic, independent of the Seman2 production parser."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from time import perf_counter

from delphin import ace
from scripts.typed_resource_poc import pinned_novel_sources
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input

EXPECTED_MANIFEST = "93bb915a30a956fef8c465a7dd684e57cfd2b2866f225409c9fd4686d0b2e5af"

def hash_file(path):
    with open(path, "rb") as stream:
        return __import__("hashlib").file_digest(stream, "sha256").hexdigest()

def observe(parser, text, cap):
    start = perf_counter()
    if "\n" in text or "\r" in text:
        return {"status": "unsupported_multiline_input", "results": [],
                "elapsed_seconds": 0}
    try:
        response = parser.interact(text)
        results = [dict(result) for result in response.results()]
        # Preserve the original MRS, UDF derivation, labels and ranking metadata.
        native = {k: v for k, v in response.items() if k not in ("results", "run")}
        usable = sum(bool(r.get("mrs") and r.get("derivation")) for r in results)
        if results and usable != len(results):
            status = "incomplete_native_output"
        elif results:
            status = "has_native_analysis"
        else:
            status = "no_analysis_returned"
        return {"status": status, "results": results, "native_response": native,
                "n_results": len(results), "result_cap_reached": len(results) >= cap,
                "elapsed_seconds": perf_counter() - start}
    except Exception as exc:
        return {"status": "interface_error", "results": [], "error": repr(exc),
                "elapsed_seconds": perf_counter() - start}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ace", type=Path, required=True)
    p.add_argument("--grammar", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--timeout", type=int, default=10)
    args = p.parse_args()
    if not 1 <= args.limit <= 1000 or args.max_results < 1 or args.timeout < 1:
        p.error("invalid limits")
    manifest, cases = pinned_novel_sources()
    if manifest != EXPECTED_MANIFEST:
        raise RuntimeError(f"Unexpected corpus manifest {manifest}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    options = ["-n", str(args.max_results), f"--timeout={args.timeout}",
               "--max-words=200", "--max-chart-megabytes=1200",
               "--max-unpack-megabytes=1500"]
    metadata = {"corpus": "Novel-1000-v3", "manifest_sha256": manifest,
                "grammar_release": "ERG 2025", "grammar_sha256": hash_file(args.grammar),
                "ace_sha256": hash_file(args.ace),
                "ace_version": subprocess.check_output([str(args.ace), "-V"],
                                                       stderr=subprocess.STDOUT, text=True).strip(),
                "pydelphin": version("pydelphin"), "ace_options": options,
                "expected_cases": 1000, "requested_cases": args.limit,
                "input_mode": "entire canonical analysis_text, no new segmentation",
                "interpretation": "Returned native analyses, not correctness or Seman2 success."}
    totals = Counter()
    groups = {}
    controls = ["The dog barks.", "She is extremely averse to delay.",
                "She is prone to errors.", "She is happy to help.",
                "I saw the man with a telescope."]
    with (args.out_dir / "ace.stderr.log").open("w") as stderr, \
            ace.ACEParser(str(args.grammar), executable=str(args.ace),
                          cmdargs=options.copy(), stderr=stderr) as parser:
        control_rows = [{"text": t, **observe(parser, t, args.max_results)}
                        for t in controls]
        (args.out_dir / "controls.json").write_text(
            json.dumps(control_rows, indent=2, ensure_ascii=False, default=str))
        if control_rows[0]["status"] != "has_native_analysis":
            raise RuntimeError("ACE smoke control did not return MRS and derivation")
        with (args.out_dir / "cases.jsonl").open("w", encoding="utf-8") as handle:
            for i, (case_id, case) in enumerate(cases[:args.limit], 1):
                text = prepare_corpus_input(case).analysis_text
                obs = observe(parser, text, args.max_results)
                row = {"case_id": case_id, "book_id": case["book_id"],
                       "source_span": case["structural_core_source_span"],
                       "source_text": text,
                       "source_sha256": sha256(text.encode("utf-8")).hexdigest(), **obs}
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                handle.flush()
                counts = Counter({obs["status"]: 1,
                                  "returned_analyses": len(obs["results"]),
                                  "at_result_cap": int(obs.get("result_cap_reached", False))})
                totals.update(counts)
                groups.setdefault(case_id.split("-")[0], Counter()).update(counts)
                if i % 25 == 0:
                    print("PROGRESS", i, dict(totals), flush=True)
    report = {**metadata, "evaluated_cases": args.limit,
              "complete_corpus": args.limit == 1000, "totals": dict(totals),
              "groups": groups}
    (args.out_dir / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    if totals["interface_error"] or totals["incomplete_native_output"]:
        raise SystemExit("Native interface failures; see artifact")

if __name__ == "__main__":
    main()
