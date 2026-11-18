"""Rebuild the Novel v3 benchmark from exact v2 anchors and original sources."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import novel_ladder as ladder
from scripts import novel_quote_source_v2 as v2
from scripts.evaluate_novel_transfer import ROOT, verify_source

DIRECTORY = ROOT / "research" / "novel_source_reporting_v3"
SCHEMA = "seman2-novel-source-reporting-v3"


def prepare(*, inventory=None):
    reference = ladder.read_json(DIRECTORY / "v2-reference.json")
    old_manifest = ladder.read_json(v2.DIRECTORY / "source-manifest.json")
    old_baseline = ladder.read_json(v2.DIRECTORY / "baseline.json")
    old_queue = ladder.read_json(v2.DIRECTORY / "novel-500-case-queue.json")
    if (reference["manifest_sha256"] != ladder.digest(old_manifest)
            or old_baseline["manifest_sha256"] != reference["manifest_sha256"]
            or reference["repair_targets"] != [r["transfer_id"] for r in old_queue["unresolved"]]):
        raise ValueError("Wrong v2 source manifest or repair queue")
    inventory, bodies, editions = (ladder.load_source_inventory()
                                   if inventory is None else inventory)
    if editions != old_manifest["editions"]:
        raise ValueError("Source editions changed")
    candidates = {v2.key(c): c for rows in inventory.values() for c in rows}
    same_paragraph = {}
    for c in candidates.values():
        same_paragraph.setdefault(ladder.source_id(c), []).append(c)
    pins = {"500": reference["legacy_anchors"]}
    pins.update({str(n): old_manifest["cohorts"][str(n)]["anchors"] for n in v2.ENDS})
    by_witness = {f"{book}:{ladder.case_hash(c)[:16]}": c
                  for book, rows in inventory.items() for c in rows}
    witnesses = [by_witness[w.case_id] for w in v2.WITNESSES]
    pins["witnesses"] = [ladder.anchor(i, v2.band_for(c), c)
                         for i, c in enumerate(witnesses, 1001)]
    if ladder.digest([v2.V2_SCHEMA, pins["witnesses"]]) != old_manifest["dialogue_witness_sha256"]:
        raise ValueError("The 30 exact dialogue witnesses changed")

    manifest = {"schema": SCHEMA, "v2_reference_commit": reference["commit"],
                "v2_manifest_sha256": reference["manifest_sha256"],
                "editions": editions, "limits": ladder.LIMITS, "sampling_tokens": [4, 32],
                "source_repairs": [], "cohorts": {}}
    groups = {}
    seen_anchors, seen_paragraphs, seen_text = set(), set(), set()
    for group, entries in pins.items():
        n = int(group) if group != "witnesses" else 1030
        size = len(entries)
        if [a[0] for a in entries] != list(range(n - size + 1, n + 1)):
            raise ValueError(f"Noncontiguous v2 anchors for {group}")
        anchors, cases = [], []
        for old in entries:
            i, book, para, a, b, band, _ = old
            c = candidates.get(v2.anchor_key(old))
            if c is None:
                # Retain the original paragraph, and take its unique eligible
                # canonical source utterance that subsumes the detached tag.
                # No completion measurement is read during source selection.
                possible = [row for row in same_paragraph.get((book, para), ())
                            if row["structural_core_source_span"][0] < a
                            and row["structural_core_source_span"][1] == b
                            and {p["function"] for p in row["structural_constituents"]}
                               >= {"direct_speech", "reporting_clause"}]
                if len(possible) != 1:
                    raise ValueError(f"No unique canonical reporting-utterance successor for {i}")
                c, = possible
                band = v2.band_for(c)
                manifest["source_repairs"].append({"v2": old, "v3": ladder.anchor(i, band, c)})
            if ladder.source_id(c) != (book, para) or v2.band_for(c) != band:
                raise ValueError(f"Source provenance or length band changed unexpectedly at {i}")
            if group != "witnesses":
                if (v2.key(c) in seen_anchors or (group != "500" and
                        (ladder.source_id(c) in seen_paragraphs or ladder.source_key(c) in seen_text))):
                    raise ValueError(f"Repeated extension paragraph or exact anchor at {i}")
                seen_anchors.add(v2.key(c))
                seen_paragraphs.add(ladder.source_id(c))
                seen_text.add(ladder.source_key(c))
            verify_source(c, bodies[book])
            anchors.append(ladder.anchor(i, band, c))
            suffix = str(i) if group != "witnesses" else f"W{i - 1000}"
            cases.append({**c, "band": band, "ladder_index": i, "transfer_id": f"Q3-{suffix}"})
        header = {"schema": SCHEMA, "first_index": cases[0]["ladder_index"],
                  "anchors": anchors, "cohort_sha256": ladder.digest([SCHEMA, anchors])}
        manifest["cohorts"][group] = {"cohort_sha256": header["cohort_sha256"],
                                        "size": size, "book_bands": _band_counts(anchors)}
        groups[group] = header, cases
    if len(seen_anchors) != 1000 or len(manifest["source_repairs"]) != 2:
        raise ValueError("Expected two reporting-boundary repairs and 998 retained benchmark sources")
    observed = [item["v2"][0] for item in manifest["source_repairs"]]
    if observed != reference["source_boundary_repairs"]:
        raise ValueError("Source-boundary repair indices differ from their audited v2 anchors")
    return manifest, groups, reference


def _band_counts(anchors):
    counts = Counter(f"{x[1]}:{x[5]}" for x in anchors)
    return dict(sorted(counts.items()))


def evaluate(manifest, groups, reference, out_dir):
    summary = {"schema": SCHEMA, "manifest_sha256": ladder.digest(manifest),
               "limits": ladder.LIMITS, "cohorts": {}}
    queue = {"schema": SCHEMA, "cohort_sha256": groups["500"][0]["cohort_sha256"],
             "last_attempted_index": max(int(x[3:]) for x in reference["repair_targets"]),
             "completed_count": 0, "unresolved": []}
    new_indexes = {int(x[3:]) for x in reference["repair_targets"]}
    new_indexes.update(reference["source_boundary_repairs"])
    for group, (header, cases) in groups.items():
        end = cases[-1]["ladder_index"]
        with (out_dir / f"novel-{end}-parses.jsonl").open(encoding="utf-8") as f:
            observed = [json.loads(line) for line in f]
        replay = ladder.read_json(out_dir / f"novel-{end}-result.json")
        if (replay["cohort_sha256"] != header["cohort_sha256"]
                or replay["limits"] != ladder.LIMITS or len(observed) != len(cases)
                or any(any(o.get(k) != v for k, v in c.items()) for o, c in zip(observed, cases))):
            raise ValueError(f"Replay does not match the canonical cohort for {group}")
        sig = ladder.signatures(observed)
        counts = dict(sorted(Counter(x["status"] for x in sig).items()))
        if sig != replay["cases"] or counts != replay["counts"]:
            raise ValueError(f"Inconsistent emitted trees and graphs for {group}")
        protected = [x for x in sig if group != "500" or x["index"] not in new_indexes]
        if (reference["protected"][group]["count"] != len(protected)
                or reference["protected"][group]["signatures_sha256"] != ladder.digest(protected)):
            raise ValueError(f"Previously selected syntax or graph signature changed in {group}")
        if (counts != {"complete": len(cases)}
                or any(not x["rank_one_sha256"] or not x["selected_graph_sha256"] for x in sig)):
            unresolved = [r["transfer_id"] for r in observed if r["status"] != "complete"]
            raise ValueError(f"Unresolved cases or missing selected outputs in {group}: {unresolved}")
        limited = [x for x in sig if x["forest_budget_exceeded"] or x["kbest_budget_exceeded"]]
        if any(group == "500" and x["index"] in new_indexes for x in limited):
            raise ValueError("A repaired case exceeded an existing search limit")
        summary["cohorts"][group] = {"counts": counts, "cohort_sha256": header["cohort_sha256"],
                                     "ordered_signatures_sha256": ladder.digest(sig),
                                     "protected": len(protected),
                                     "inherited_search_limit_flags": len(limited)}
        if group == "500":
            queue["completed_count"] = len(sig)
    return summary, queue


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("plan", "replay", "pin", "check"))
    p.add_argument("--wordnet-dir", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--group", choices=tuple(v2.REPLAY_GROUPS), default="all")
    args = p.parse_args()
    manifest, groups, reference = prepare()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.action == "plan":
        ladder.write_json(args.out_dir / "source-manifest.json", manifest)
        return
    pin = DIRECTORY / "source-manifest.json"
    if (pin.exists() or args.action == "check") and ladder.read_json(pin) != manifest:
        raise ValueError("Canonical source manifest no longer matches the revision")
    if args.action in ("pin", "check"):
        summary, queue = evaluate(manifest, groups, reference, args.out_dir)
        for name, obj in (("baseline.json", summary), ("novel-500-case-queue.json", queue)):
            if args.action == "pin":
                ladder.write_json(args.out_dir / name, obj)
            elif obj != ladder.read_json(DIRECTORY / name):
                raise ValueError(f"Unexpected replay outputs for {name}")
        print("Q3_REPLAY", {g: row["counts"] for g, row in summary["cohorts"].items()}, flush=True)
        return
    if args.wordnet_dir is None:
        p.error("replay requires --wordnet-dir")
    for batch in v2.REPLAY_GROUPS[args.group]:
        ladder.run([groups[g] for g in batch], args.wordnet_dir, args.out_dir)


if __name__ == "__main__":
    main()
