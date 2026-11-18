"""Measure the clipped-apostrophe source revision, beside the immutable v1 pins."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, analysis_units, tokenize
from scripts import novel_ladder as ladder
from scripts.audit_anchored_dialogue_30 import WITNESSES
from scripts.audit_context_dependencies import fingerprint
from scripts.diagnose_novel_parses import select_cases
from scripts.novel1000_exploratory import CANDIDATE_DIR
from scripts.evaluate_novel_transfer import ROOT, verify_source

DIRECTORY = ROOT / "research" / "novel_source_quote_v2"
V2_SCHEMA = "seman2-novel-source-clipped-apostrophe-v2"
ENDS = (600, 700, 800, 900, 1000)
V1_COMMIT = "3d919b063b7ab6e3430cee51d23358a5d97aa851"
HISTORICAL_800 = ROOT / "research" / "novel_800_exploration"


REPLAY_GROUPS = {
    "500": (("500",),), "600-700": (("600", "700"),), "800": (("800",),),
    "900-1000": (("900", "1000"),), "witnesses": (("witnesses",),),
}
REPLAY_GROUPS["all"] = tuple(batch for batches in REPLAY_GROUPS.values() for batch in batches)


def original_paths(end):
    if end <= 700:
        prefix = ladder.LADDER / f"novel-{end}"
    else:
        folder = HISTORICAL_800 if end == 800 else CANDIDATE_DIR
        prefix = folder / f"novel-{end}-candidate"
    return Path(str(prefix) + "-cohort.json"), Path(str(prefix) + "-current.json")


def key(case):
    return (case["book_id"], *case["structural_core_source_span"], ladder.case_hash(case))


def anchor_key(anchor):
    _, book, _, begin, end, _, source_sha = anchor
    return book, begin, end, source_sha


def band_for(case):
    return next(band for band, lo, hi in ladder.BANDS if lo <= case["tokens"] <= hi)


def selection_rank(first, case):
    start = case["structural_core_source_span"][0]
    return ladder.digest(["novel-ladder-selection-v1", first, case["book_id"], start]), start


def choose(legacy, available, originals):
    """Reserve all eligible old sources first, then fill exact deficits by hash.

    The old indices are used only to audit displaced source identities. New
    indices follow book, band, and the deterministic source rank in this revision.
    This step never reads a grammar result.
    """
    taken_para = {ladder.source_id(c) for c in legacy}
    taken_text = {ladder.source_key(c) for c in legacy}
    kept, missing, removed = {}, {}, {}
    by_key = {key(c): c for rows in available.values() for c in rows}

    def excluded(c):
        return ladder.source_id(c) in taken_para or ladder.source_key(c) in taken_text

    def reserve(c):
        taken_para.add(ladder.source_id(c))
        taken_text.add(ladder.source_key(c))

    for end, anchors in originals.items():
        kept[end], missing[end], removed[end] = [], [], []
        for old in anchors:
            _, book, para, _, _, band, _ = old
            c = by_key.get(anchor_key(old))
            if c is None:
                reason = "no_longer_eligible_at_original_boundary"
            elif c["structural_paragraph_index"] != para or band_for(c) != band:
                reason = "source_provenance_or_band_changed"
            elif excluded(c):
                reason = "duplicates_resampled_or_retained_source"
            else:
                reserve(c)
                kept[end].append((band, c))
                continue
            missing[end].append((book, band))
            removed[end].append({"v1_anchor": old, "reason": reason})
    new = {}
    for end, deficits in missing.items():
        first = end - 99
        new[end] = []
        for book, band in deficits:
            pool = sorted(
                (c for c in available[book] if band_for(c) == band),
                key=lambda c: selection_rank(first, c),
            )
            c = next((x for x in pool if not excluded(x)), None)
            if c is None:
                raise ValueError(f"No disjoint revision source for {book} {band}")
            reserve(c)
            new[end].append((band, c))
    return kept, new, removed


def prepare():
    legacy, _ = select_cases(500)
    available, bodies, editions = ladder.load_source_inventory()
    manifests = {end: ladder.read_json(original_paths(end)[0]) for end in ENDS}
    kept, new, removed = choose(legacy, available, {end: m["anchors"] for end, m in manifests.items()})
    result = {
        "schema": V2_SCHEMA,
        "v1_reference_commit": V1_COMMIT,
        "v1_legacy_500_sha256": ladder.EXPECTED_500_COHORT_SHA256,
        "legacy_500_sha256": fingerprint(legacy),
        "sampling_tokens": [4, 32],
        "limits": ladder.LIMITS,
        "editions": editions,
        "cohorts": {},
    }
    groups = {}
    for end in ENDS:
        first = end - 99
        rows = sorted([*kept[end], *new[end]],
                      key=lambda e: (e[1]["book_id"], e[0], selection_rank(first, e[1])))
        if (len(rows) != 100 or set(Counter(c["book_id"] for _, c in rows).values()) != {25}
                or set(Counter(b for b, _ in rows).values()) != {25}):
            raise ValueError(f"Revision violates original book/band quotas at {end}")
        pairs = [(i, band, c) for i, (band, c) in enumerate(rows, first)]
        anchors = [ladder.anchor(i, b, c) for i, b, c in pairs]
        fresh = {key(c) for _, c in new[end]}
        cohort = {
            "schema": V2_SCHEMA,
            "first_index": first,
            "cohort_sha256": ladder.digest([V2_SCHEMA, anchors]),
            "anchors": anchors,
            "v1_cohort_sha256": manifests[end]["cohort_sha256"],
            "removed": removed[end],
            "replacement_anchors": [a for a in anchors if anchor_key(a) in fresh],
        }
        result["cohorts"][str(end)] = cohort
        groups[str(end)] = (cohort, [
            {**c, "band": band, "ladder_index": i, "transfer_id": f"Q2-{i}"} for i, band, c in pairs
        ])
    legacy_anchors = [ladder.anchor(i, c["band"], c) for i, c in enumerate(legacy, 1)]
    groups["500"] = (
        {"schema": V2_SCHEMA, "cohort_sha256": result["legacy_500_sha256"], "anchors": legacy_anchors},
        [{**c, "ladder_index": i, "transfer_id": f"Q2-{i}"} for i, c in enumerate(legacy, 1)],
    )

    # Locate the exact dialogue witnesses by their historical source keys, not
    # by their old Novel-500 indices, which are invalid under resampling.
    source_by_witness = {}
    for book, rows in available.items():
        for c in rows:
            source_by_witness[f"{book}:{ladder.case_hash(c)[:16]}"] = c
    witnesses = [source_by_witness[w.case_id] for w in WITNESSES]
    witness_anchors = [ladder.anchor(i, band_for(c), c) for i, c in enumerate(witnesses, 1001)]
    result["dialogue_witness_sha256"] = ladder.digest([V2_SCHEMA, witness_anchors])
    groups["witnesses"] = (
        {"schema": V2_SCHEMA, "cohort_sha256": result["dialogue_witness_sha256"], "anchors": witness_anchors},
        [{**c, "ladder_index": i, "transfer_id": f"Q2-W{i-1000}"} for i, c in enumerate(witnesses, 1001)],
    )
    for _, rows in groups.values():
        for case in rows:
            verify_source(case, bodies[case["book_id"]])
    return result, groups


def source_defect():
    v1 = ladder.read_json(original_paths(1000)[0])
    old = next(a for a in v1["anchors"] if a[0] == 952)
    _, book, _, start, stop, _, _ = old
    edition = next(b for b in TRAIN_BOOKS if b.ebook_id == book)
    text, _ = load_cleaned(edition)
    unit = next(u for u in analysis_units(text) if u.core_start == start)
    count = len(tokenize(unit.source_text))
    if (unit.core_end <= stop or unit.quotation_status != "balanced" or count <= 32
            or unit.synthetic_prefix or unit.synthetic_suffix or unit.synthetic_terminal
            or " ".join(text[unit.core_start:unit.core_end].split()) != unit.source_text):
        raise ValueError("The complete source no longer supports the clipping diagnosis")
    return {
        "v1_anchor": old, "corrected_core_span": [unit.core_start, unit.core_end],
        "corrected_source_sha256": ladder.case_hash({"source_text": unit.source_text}),
        "corrected_tokens": count, "status": "source_boundary_corrected_beyond_sampling_limit",
    }


def measured_revision(manifests, groups, replay_dir):
    """Validate the measured inputs and assemble separate revision pins."""
    baseline = {"schema": V2_SCHEMA, "manifest_sha256": ladder.digest(manifests),
                "limits": ladder.LIMITS, "cohorts": {}, "prior_anchors": {}}
    queue = None
    for group, (manifest, cases) in groups.items():
        end = cases[-1]["ladder_index"]
        with (replay_dir / f"novel-{end}-parses.jsonl").open(encoding="utf-8") as stream:
            output = [json.loads(line) for line in stream]
        result = ladder.read_json(replay_dir / f"novel-{end}-result.json")
        if (len(cases) != len(output)
                or result["cohort_sha256"] != manifest["cohort_sha256"]
                or result["limits"] != ladder.LIMITS):
            raise ValueError(f"Wrong replay source, size or limits for {group}")
        for case, observed in zip(cases, output):
            if any(observed.get(k) != v for k, v in case.items()):
                raise ValueError(f"Replay source/provenance changed at {case['transfer_id']}")
        signatures = ladder.signatures(output)
        counts = dict(sorted(Counter(r["status"] for r in output).items()))
        if signatures != result["cases"] or counts != result["counts"]:
            raise ValueError(f"Replay result does not match emitted parse data for {group}")
        if any((r["status"] == "complete") != bool(r["rank_one_sha256"] and r["selected_graph_sha256"])
               for r in signatures):
            raise ValueError(f"Missing tree or graph for a completed parse in {group}")
        if "error" in counts:
            raise ValueError(f"Execution error in {group}; not a grammar baseline")
        baseline["cohorts"][group] = {
            "cohort_sha256": manifest["cohort_sha256"], "counts": counts,
            "ordered_signatures_sha256": ladder.digest(signatures),
        }
        if group == "500":
            queue = {
                "schema": "seman2-novel-source-v2-case-queue-v1",
                "cohort_sha256": manifest["cohort_sha256"],
                "completed_count": counts.get("complete", 0),
                "last_attempted_index": -1,
                "unresolved": [
                    {"index": i, "transfer_id": c["transfer_id"], "book_id": c["book_id"],
                     "source_sha256": ladder.case_hash(c), "status": r["status"]}
                    for i, (c, r) in enumerate(zip(cases, signatures)) if r["status"] != "complete"
                ],
            }
        elif group != "witnesses":
            old_cohort, old_results = map(ladder.read_json, original_paths(int(group)))
            old_rows = {a[0]: r for a, r in zip(old_cohort["anchors"], old_results["cases"])}
            before = {anchor_key(a): (a, old_rows[a[0]]) for a in old_cohort["anchors"]}
            matches, changes = 0, []
            for c, after in zip(cases, signatures):
                pair = before.get(key(c))
                if pair is None:
                    continue
                matches += 1
                anchor, old = pair
                if old["status"] == "complete" and after["status"] != "complete":
                    raise ValueError(f"Retained source lost its selected parse: {c['transfer_id']}")
                if {k: v for k, v in after.items() if k != "index"} != {
                    k: v for k, v in old.items() if k != "index"
                }:
                    changes.append({"v1_anchor": anchor, "v2_id": c["transfer_id"],
                                    "v1_root": old["root_rule"], "v2_root": after["root_rule"]})
            baseline["prior_anchors"][group] = {
                "matched": matches, "selected_signature_changes": changes,
            }
    if baseline["cohorts"]["witnesses"]["counts"] != {"complete": 30}:
        raise ValueError("A historical dialogue witness no longer completes")
    return baseline, queue


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("plan", "replay", "pin", "check"))
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--wordnet-dir", type=Path)
    p.add_argument("--group", choices=tuple(REPLAY_GROUPS))
    args = p.parse_args()
    manifests, groups = prepare()
    manifests["source_defect"] = source_defect()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.action == "plan":
        ladder.write_json(args.out_dir / "source-manifest.json", manifests)
        return
    pin_path = DIRECTORY / "source-manifest.json"
    if (args.action == "check" or pin_path.exists()) and ladder.read_json(pin_path) != manifests:
        raise ValueError("Versioned source manifest differs from canonical extraction")
    if args.action in ("pin", "check"):
        baseline, queue = measured_revision(manifests, groups, args.out_dir)
        for name, data in (("baseline.json", baseline), ("novel-500-case-queue.json", queue)):
            if args.action == "pin":
                ladder.write_json(args.out_dir / name, data)
            elif ladder.read_json(DIRECTORY / name) != data:
                raise ValueError(f"Versioned replay differs from {name}")
        print("Q2_REPLAY", {g: row["counts"] for g, row in baseline["cohorts"].items()}, flush=True)
        return
    if args.group is None or args.wordnet_dir is None:
        p.error("replay requires --group and --wordnet-dir")
    for batch in REPLAY_GROUPS[args.group]:
        ladder.run([groups[k] for k in batch], args.wordnet_dir, args.out_dir)


if __name__ == "__main__":
    main()
