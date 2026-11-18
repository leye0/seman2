"""Source-frozen exploratory Novel-900 and Novel-1000, without premature acceptance.

N801-N900 and N901-N1000 are distinct 100-case extensions of the original
four cleaned Gutenberg books. Source selection never consults parse success.
The source and parser limits are exactly those of the existing Novel Ladder.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import signal

from scripts import novel_ladder as ladder
from scripts.evaluate_novel_transfer import ROOT, _deadline, measure
from seman_parser.engine import Parser, ParserResources

CANDIDATE_DIR = ROOT / "research" / "novel_1000_exploration"
PREVIOUS_800_DIR = ROOT / "research" / "novel_800_exploration"
ENDS = (900, 1000)
SCHEMA = ladder.SCHEMA


def candidate_path(end: int, suffix: str) -> Path:
    return CANDIDATE_DIR / f"novel-{end}-candidate-{suffix}.json"


def verify_predecessors(sources):
    """Require real selected syntax/graph reviews, not 100% recognition alone."""
    cohorts, paragraphs, texts = ladder.read_ladder(ladder.LADDER, sources)
    if [cases[-1]["ladder_index"] for _, cases in cohorts] != [600, 700]:
        raise ValueError("Frozen Novel-600 and Novel-700 must precede exploration")
    for manifest, cases in cohorts:
        end = cases[-1]["ladder_index"]
        tag = "accepted" if end == 600 else "current"
        result = ladder.read_json(ladder.LADDER / f"novel-{end}-{tag}.json")
        reviews = ladder.load_review(ladder.LADDER, end, manifest, result)
        ladder.accepted_cases(result, manifest, end, reviews)

    # The existing N800 is still exploratory. It can be used for SOURCE
    # exclusion, but must not silently be promoted to a production rung.
    selected = ladder.pick(sources[1], paragraphs, texts, 701)
    expected_anchors = [ladder.anchor(i, b, c) for i, b, c in selected]
    manifest = ladder.read_json(PREVIOUS_800_DIR / "novel-800-candidate-cohort.json")
    if (manifest.get("anchors") != expected_anchors
            or manifest.get("cohort_sha256") != ladder.digest(expected_anchors)):
        raise ValueError("Novel-800 frozen sources differ from deterministic selection")
    previous = ladder.resolve(manifest, 701, sources)
    result = ladder.read_json(PREVIOUS_800_DIR / "novel-800-candidate-current.json")
    rows = ladder.result_cases(result, manifest, 800)
    review = ladder.read_json(PREVIOUS_800_DIR / "novel-800-candidate-review.json")
    if (review.get("schema") != ladder.REVIEW_SCHEMA
            or review.get("cohort_sha256") != manifest["cohort_sha256"]
            or len(review.get("cases", [])) != 100
            or ladder.known_semantic_defects(800)):
        raise ValueError("Novel-800 is not fully reviewed or has known defects")
    seen = set()
    for entry in review["cases"]:
        i = entry.get("index")
        row = rows.get(i)
        if (i in seen or row is None or row["status"] != "complete"
                or entry.get("verdict") != "verified"
                or not str(entry.get("evidence", "")).strip()
                or entry.get("rank_one_sha256") != row["rank_one_sha256"]
                or entry.get("selected_graph_sha256") != row["selected_graph_sha256"]
                or not row["selected_graph_sha256"]):
            raise ValueError(f"Invalid or stale Novel-800 semantic review: {i}")
        seen.add(i)
    if seen != set(range(701, 801)):
        raise ValueError("Novel-800 reviews must cover all 100 source IDs")

    for case in previous:
        key = ladder.source_id(case)
        identity = ladder.source_key(case)
        if key in paragraphs or identity in texts:
            raise ValueError("N800 reuses a prior source paragraph or text")
        paragraphs.add(key)
        texts.add(identity)
    return paragraphs, texts


def build_manifest(sources, paragraphs, texts, first):
    selected = ladder.pick(sources[1], paragraphs, texts, first)
    anchors = [ladder.anchor(i, band, case) for i, band, case in selected]
    manifest = {
        "schema": SCHEMA,
        "first_index": first,
        "legacy_cohort_sha256": ladder.EXPECTED_500_COHORT_SHA256,
        "editions": sources[3],
        "cohort_sha256": ladder.digest(anchors),
        "anchors": anchors,
    }
    cases = ladder.resolve(manifest, first, sources)
    if (sorted(Counter(c["book_id"] for c in cases).values()) != [25] * 4
            or sorted(Counter(c["band"] for c in cases).values()) != [25] * 4):
        raise ValueError("The 4 books and 4 length bands must each contribute 25")
    for case in cases:
        key = ladder.source_id(case)
        identity = ladder.source_key(case)
        if key in paragraphs or identity in texts:
            raise ValueError(f"Reused source in N{case['ladder_index']}")
        paragraphs.add(key)
        texts.add(identity)
    return manifest, cases


def stage(sources):
    paragraphs, texts = verify_predecessors(sources)
    cohorts = []
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    for end in ENDS:
        manifest, cases = build_manifest(sources, paragraphs, texts, end - 99)
        path = candidate_path(end, "cohort")
        if path.exists():
            if ladder.read_json(path) != manifest:
                raise ValueError(f"Novel-{end} immutable source manifest drift")
        else:
            ladder.write_json(path, manifest)
        cohorts.append((end, manifest, cases))
        print(f"N{end}_COHORT_SHA256 {manifest['cohort_sha256']}", flush=True)
    return cohorts


def preserve_initial(path, value):
    """Never silently replace an immutable initial measurement."""
    if path.exists():
        if ladder.read_json(path) != value:
            raise ValueError(f"Initial baseline or selected result changed: {path}")
    else:
        ladder.write_json(path, value)


def run(wordnet_dir: Path, out_dir: Path):
    cohorts = stage(ladder.load_sources())
    out_dir.mkdir(parents=True, exist_ok=True)
    parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir),
                    cache_size=0, max_items=ladder.MAX_ITEMS)
    parser.parse("John opened the box.")
    previous = signal.signal(signal.SIGALRM, _deadline)
    try:
        for end, manifest, cases in cohorts:
            rows = []
            with (out_dir / f"novel-{end}-candidate-parses.jsonl").open(
                "w", encoding="utf-8", buffering=1,
            ) as stream:
                for case in cases:
                    measured = {**case, **measure(parser, case, with_semantics=True)}
                    stream.write(json.dumps(measured, ensure_ascii=False) + "\n")
                    rows.append(measured)
                    print("NOVEL_1000_CASE", json.dumps({
                        "index": case["ladder_index"], "status": measured["status"],
                        "root": measured.get("root_rule"),
                        "forest_budget": measured.get("forest_budget_exceeded", False),
                        "kbest_budget": measured.get("kbest_budget_exceeded", False),
                    }, ensure_ascii=False, separators=(",", ":")), flush=True)

            counts = dict(sorted(Counter(r["status"] for r in rows).items()))
            result = {
                "schema": "seman2-novel-ladder-result-v1",
                "cohort_sha256": manifest["cohort_sha256"],
                "limits": ladder.LIMITS,
                "counts": counts,
                "cases": ladder.signatures(rows),
            }
            ladder.result_cases(result, manifest, end)
            summary = {
                "schema": "seman2-novel-exploration-summary-v1",
                "cohort_sha256": manifest["cohort_sha256"],
                "accepted": False,
                "semantic_verified": 0,
                "source_count": 100,
                "counts": counts,
                "by_book": {str(k): dict(Counter(r["status"] for r in rows
                    if r["book_id"] == k)) for k in sorted({r["book_id"] for r in rows})},
                "by_band": {str(k): dict(Counter(r["status"] for r in rows
                    if r["band"] == k)) for k in sorted({r["band"] for r in rows})},
                "incomplete": [
                    {"index": r["ladder_index"], "book_id": r["book_id"],
                     "status": r["status"], "source_text": r["source_text"],
                     "source_span": r["structural_core_source_span"],
                     "forest_budget_exceeded": r.get("forest_budget_exceeded", False),
                     "kbest_budget_exceeded": r.get("kbest_budget_exceeded", False)}
                    for r in rows if r["status"] != "complete"
                ],
            }
            ladder.write_json(out_dir / f"novel-{end}-candidate-result.json", result)
            ladder.write_json(out_dir / f"novel-{end}-candidate-summary.json", summary)
            preserve_initial(candidate_path(end, "initial"), result)
            preserve_initial(candidate_path(end, "current"), result)
            review_path = candidate_path(end, "review")
            empty_review = {"schema": ladder.REVIEW_SCHEMA,
                            "cohort_sha256": manifest["cohort_sha256"], "cases": []}
            if not review_path.exists():
                ladder.write_json(review_path, empty_review)
            elif ladder.read_json(review_path)["cohort_sha256"] != manifest["cohort_sha256"]:
                raise ValueError(f"Novel-{end} review source drift")
            print(f"Novel-{end}: {counts}; independently reviewed: 0/100", flush=True)
    finally:
        signal.signal(signal.SIGALRM, previous)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("stage", "run"))
    cli.add_argument("--wordnet-dir", type=Path)
    cli.add_argument("--out-dir", type=Path)
    args = cli.parse_args()
    if args.action == "stage":
        stage(ladder.load_sources())
    else:
        if args.wordnet_dir is None or args.out_dir is None:
            cli.error("run requires --wordnet-dir and --out-dir")
        run(args.wordnet_dir, args.out_dir)


if __name__ == "__main__":
    main()
