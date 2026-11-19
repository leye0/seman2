"""Extend frozen Novel-1000 v3 with 500 independently sampled Gutenberg cases."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts import novel_ladder as ladder
from scripts import novel_source_reporting_v3 as parent
from scripts.novel_quote_source_v2 import selection_rank
from scripts.evaluate_novel_transfer import ROOT, verify_source

DIRECTORY = ROOT / "research" / "novel_1500_exploration"
SCHEMA = "seman2-novel1500-exploration-v1"
ENDS = (1100, 1200, 1300, 1400, 1500)
REPAIR_SCHEMA = "seman2-novel1500-verified-repairs-v1"
CENSORED_STATUSES = frozenset({"timeout", "forest_budget_exceeded",
                               "kbest_budget_exceeded", "both_budgets_exceeded"})


# Per-rung margins remain 25 passages per book and 25 per length band.
# The inherited diagonal allocation needs 35 independent short Frankenstein
# paragraphs. Only one remains. Trade those slots against longer cells.
QUOTAS = {84: (0, 7, 9, 9), 120: (8, 6, 5, 6),
          766: (8, 6, 6, 5), 1342: (9, 6, 5, 5)}
FIRST_RUNG_QUOTAS = {**QUOTAS, 84: (1, 6, 9, 9), 1342: (8, 7, 5, 5)}


def select_extensions(inventory, paragraphs, texts):
    """Match all requested cells to distinct paragraphs before assigning indices."""
    if set(inventory) != set(QUOTAS):
        raise ValueError("Unexpected editions in Novel-1500 source inventory")
    chosen = {end: [] for end in ENDS}
    eligible = {book: [] for book in inventory}
    seen_texts = set(texts)
    for book, rows in sorted(inventory.items()):
        for row in sorted(rows, key=lambda c: c["structural_core_source_span"]):
            identity = ladder.source_key(row)
            if ladder.source_id(row) not in paragraphs and identity not in seen_texts:
                eligible[book].append(row)
                seen_texts.add(identity)

    for book, rows in eligible.items():
        pools, slots = {}, []
        for band_offset, (band, low, high) in enumerate(ladder.BANDS):
            for end in ENDS:
                quotas = FIRST_RUNG_QUOTAS if end == ENDS[0] else QUOTAS
                quota = quotas[book][band_offset]
                if not quota:
                    continue
                first = end - ladder.SIZE + 1
                pools[end, band] = sorted((r for r in rows if low <= r["tokens"] <= high),
                                          key=lambda case: selection_rank(first, case))
                slots.extend((end, band, position) for position in range(quota))

        owners, assignments = {}, {}

        def assign(slot, visited):
            end, band, _ = slot
            for candidate in pools[end, band]:
                paragraph = ladder.source_id(candidate)
                if paragraph in visited:
                    continue
                visited.add(paragraph)
                prior = owners.get(paragraph)
                if prior is None or assign(prior, visited):
                    owners[paragraph] = slot
                    assignments[slot] = candidate
                    return True
            return False

        # Attempt unowned choices first to retain the hash-ranked greediness in
        # unconstrained cells. An augmenting path is necessary when two cells
        # compete for the same otherwise usable paragraph.
        for slot in sorted(slots, key=lambda s: (len(pools[s[:2]]), s)):
            free = next((r for r in pools[slot[:2]] if ladder.source_id(r) not in owners), None)
            if free is not None:
                owners[ladder.source_id(free)] = slot
                assignments[slot] = free
            elif not assign(slot, set()):
                raise ValueError(f"Cannot match Novel-{slot[0]} source quota for {book} in {slot[1]}")
        for (end, band, _), row in assignments.items():
            chosen[end].append((band, row))
    for end, selected in chosen.items():
        selected.sort(key=lambda item: (item[1]["book_id"], item[0],
                                        selection_rank(end - ladder.SIZE + 1, item[1])))
    return chosen


def prepare(*, inventory=None):
    inventory, bodies, editions = (ladder.load_source_inventory()
                                   if inventory is None else inventory)
    parent_manifest, preceding, _ = parent.prepare(inventory=(inventory, bodies, editions))
    if parent_manifest != ladder.read_json(parent.DIRECTORY / "source-manifest.json"):
        raise ValueError("Novel-1000 v3 source changed")
    previous = [case for _, cases in preceding.values() for case in cases]
    paragraphs = {ladder.source_id(case) for case in previous}
    texts = {ladder.source_key(case) for case in previous}
    source_manifest = {
        "schema": SCHEMA,
        "novel1000_v3_manifest_sha256": ladder.digest(parent_manifest),
        "editions": editions,
        "limits": ladder.LIMITS,
        "cohorts": {},
    }
    picked = select_extensions(inventory, paragraphs, texts)
    groups = {}
    for end, selections in picked.items():
        first = end - ladder.SIZE + 1
        selected = [(index, band, row)
                    for index, (band, row) in enumerate(selections, first)]
        anchors = [ladder.anchor(i, band, row) for i, band, row in selected]
        cohort = {"first_index": first, "cohort_sha256": ladder.digest([SCHEMA, anchors]),
                  "anchors": anchors}
        cases = []
        for index, band, row in selected:
            case = {**row, "ladder_index": index, "band": band, "transfer_id": f"N{index}"}
            verify_source(case, bodies[row["book_id"]])
            cases.append(case)
        if (sorted(Counter(c["book_id"] for c in cases).values()) != [25] * 4
                or sorted(Counter(c["band"] for c in cases).values()) != [25] * 4):
            raise ValueError(f"Book or length-band quotas changed at Novel-{end}")
        source_manifest["cohorts"][str(end)] = cohort
        groups[end] = cohort, cases
    return source_manifest, groups


def replay(groups, wordnet_dir, out_dir):
    # Dynamic WordNet entries populate a lexicon's surface and morphology
    # indexes on lookup. Reusing one parser across groups can therefore
    # change selected lexical entries compared to a standalone group.
    # Freeze the same fresh-parser boundary for both invocation modes.
    for group in groups.values():
        ladder.run([group], wordnet_dir, out_dir)


def checked_observation(end, group, out_dir):
    cohort, cases = group
    result = ladder.read_json(out_dir / f"novel-{end}-result.json")
    with (out_dir / f"novel-{end}-parses.jsonl").open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    if len(rows) != len(cases) or any(
            any(observed.get(k) != v for k, v in case.items())
            for observed, case in zip(rows, cases)):
        raise ValueError(f"Wrong input provenance in Novel-{end} replay")
    signatures = ladder.result_cases(result, cohort, end)
    if (list(signatures.values()) != ladder.signatures(rows)
            or any("selected_graph_sha256" not in row or row["status"] == "error"
                   for row in signatures.values())):
        raise ValueError(f"Replay status, trees or graphs are inconsistent in Novel-{end}")
    return result, rows


def check_result(end, manifest, expected, observed):
    before = ladder.result_cases(expected, manifest, end)
    after = ladder.result_cases(observed, manifest, end)
    changed = []
    for index, row in before.items():
        if row == after[index]:
            continue
        # Timeout versus a deterministic item/k-best stop depends on runner
        # speed. Both are unresolved, never counted as a completed parse.
        replay = after[index]
        if (row["status"] in CENSORED_STATUSES and replay["status"] in CENSORED_STATUSES
                and "timeout" in {row["status"], replay["status"]}):
            continue
        changed.append(index)
    if changed:
        raise ValueError(f"Novel-{end} replay changed pinned results: {changed}")


def check_transfer(groups, repairs, review_pass, baseline_dir, candidate_dir):
    """Check a repair batch on top of an intervening, already audited revision.

    The historical pins still establish which exact sources were complete and
    which trees were selected. The intervening revision can have reviewed
    graph changes of its own. Freeze those graphs from its fresh replay
    instead of repinning, weakening or discarding their signatures.
    """
    new = {index: row for index, row in repairs.items() if row.get("review_pass") == review_pass}
    if not new:
        raise ValueError(f"No registered repairs for {review_pass}")
    previous = {index: row for index, row in repairs.items() if index not in new}
    counts = Counter()
    for end, group in groups.items():
        header, _ = group
        before, _ = checked_observation(end, group, baseline_dir)
        after, _ = checked_observation(end, group, candidate_dir)
        recorded = ladder.result_cases(expected_result(end, header, previous), header, end)
        observed = ladder.result_cases(before, header, end)
        expected = dict(observed)
        for index, row in observed.items():
            prior = recorded[index]
            if (row["status"] == "complete") != (prior["status"] == "complete") or any(
                row[key] != prior[key] for key in ("root_rule", "rank_one_sha256")
            ):
                raise ValueError(f"Baseline complete status or selected tree drifted at N{index}")
            if index in new:
                if row != new[index]["before"] or row["status"] == "complete":
                    raise ValueError(f"Transfer target was not the expected failure at N{index}")
                expected[index] = new[index]["after"]
        pinned = {**before, "cases": list(expected.values()),
                  "counts": dict(Counter(row["status"] for row in expected.values()))}
        check_result(end, header, pinned, after)
        counts["sources"] += len(expected)
        counts["complete_before"] += before["counts"].get("complete", 0)
        counts["complete_after"] += after["counts"].get("complete", 0)
    if counts["complete_after"] - counts["complete_before"] != len(new):
        raise ValueError("A registered transfer repair was not verified")
    return {**counts, "recovered": sorted(new)}


def repair_queue(source_manifest, groups, out_dir):
    unresolved = []
    for end, group in groups.items():
        _, rows = checked_observation(end, group, out_dir)
        for row in rows:
            if row["status"] != "complete":
                unresolved.append({
                    "index": row["ladder_index"], "status": row["status"],
                    "book_id": row["book_id"], "band": row["band"],
                    "paragraph": row["structural_paragraph_index"],
                    "source_span": row["structural_core_source_span"],
                    "source_sha256": ladder.case_hash(row),
                })
    return {"schema": SCHEMA, "manifest_sha256": ladder.digest(source_manifest),
            "unresolved": unresolved}


def read_repairs(source_manifest):
    data = ladder.read_json(DIRECTORY / "verified-repairs.json")
    if (data["schema"] != REPAIR_SCHEMA
            or data["manifest_sha256"] != ladder.digest(source_manifest)
            or data["limits"] != ladder.LIMITS):
        raise ValueError("Repairs do not refer to the frozen sources and limits")
    repairs = {}
    for entry in data["repairs"]:
        index = entry["before"]["index"]
        after = entry["after"]
        if (index in repairs or not 1001 <= index <= ENDS[-1] or after["index"] != index
                or after["status"] != "complete" or after["forest_budget_exceeded"]
                or after["kbest_budget_exceeded"] or not after["root_rule"]
                or not after["rank_one_sha256"] or not after["selected_graph_sha256"]
                or entry["before"] == after):
            raise ValueError(f"Unproved or invalid correction registration at N{index}")
        repairs[index] = entry
    return repairs


def expected_result(end, cohort, repairs):
    initial = ladder.read_json(DIRECTORY / f"novel-{end}-initial.json")
    by_index = ladder.result_cases(initial, cohort, end)
    for index in by_index.keys() & repairs.keys():
        entry = repairs[index]
        if by_index[index] != entry["before"]:
            raise ValueError(f"Initial signature drift at N{index}")
        source_sha = cohort["anchors"][index - cohort["first_index"]][-1]
        if entry["source_sha256"] != source_sha:
            raise ValueError(f"Repair refers to a different source at N{index}")
        by_index[index] = entry["after"]
    current = {**initial, "cases": list(by_index.values()),
               "counts": dict(Counter(row["status"] for row in by_index.values()))}
    ladder.result_cases(current, cohort, end)
    return current


def current_queue(source_manifest, repairs):
    queue = ladder.read_json(DIRECTORY / "repair-queue.json")
    if queue["manifest_sha256"] != ladder.digest(source_manifest):
        raise ValueError("Initial queue does not refer to frozen sources")
    original = queue["unresolved"]
    for row in original:
        repair = repairs.get(row["index"])
        if repair and (repair["before"]["status"] != row["status"]
                       or repair["source_sha256"] != row["source_sha256"]):
            raise ValueError(f"Unable to reconcile repaired N{row['index']} with its source")
    pending = [row for row in original if row["index"] not in repairs]
    return {**queue, "coverage_repairs": len(original) - len(pending), "unresolved": pending}


def inspect_case(index, groups, bodies, replay_dir=None):
    end = ((index + ladder.SIZE - 1) // ladder.SIZE) * ladder.SIZE
    group = groups[end]
    _, cases = group
    case = cases[(index - 1) % ladder.SIZE]
    begin, stop = case["structural_core_source_span"]
    body = bodies[case["book_id"]]
    # Use the active extractor's blank-line delimiters, including their widths.
    previous = 0
    for separator in re.finditer(r"\n\s*\n", body):
        if separator.start() >= stop:
            following = separator.start()
            break
        if separator.end() > begin:
            raise ValueError(f"N{index} overlaps a paragraph boundary")
        previous = separator.end()
    else:
        following = len(body)
    data = {
        "case": case, "source_paragraph": body[previous:following],
        "source_paragraph_span": [previous, following],
    }
    result = ladder.read_json(DIRECTORY / f"novel-{end}-initial.json")
    data["initial_signature"] = ladder.result_cases(result, group[0], end)[index]
    if replay_dir is not None:
        _, rows = checked_observation(end, group, replay_dir)
        row = rows[(index - 1) % ladder.SIZE]
        data["replay"] = {key: value for key, value in row.items() if key not in case}
    return data


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("plan", "replay", "check", "check-transfer", "snapshot", "inspect", "queue"))
    cli.add_argument("--wordnet-dir", type=Path)
    cli.add_argument("--out-dir", type=Path, help="Replay directory, optional for inspect")
    cli.add_argument("--baseline-dir", type=Path, help="Before replay for check-transfer")
    cli.add_argument("--review-pass", help="Registered repair pass for check-transfer")
    cli.add_argument("--group", choices=ENDS, type=int)
    cli.add_argument("--index", type=int, help="Frozen case index for inspect, defaults to first open case")
    args = cli.parse_args()
    if args.group is not None and args.action not in {"check", "replay"}:
        cli.error("--group requires replay or check")
    if args.index is not None and (args.action != "inspect" or not 1001 <= args.index <= ENDS[-1]):
        cli.error("--index requires inspect and an index from 1001 to 1500")
    if args.action not in {"inspect", "queue"} and args.out_dir is None:
        cli.error("--out-dir is required except for inspect and queue")
    if args.action == "replay" and args.wordnet_dir is None:
        cli.error("replay requires --wordnet-dir")
    if args.action == "check-transfer" and (args.baseline_dir is None or args.review_pass is None):
        cli.error("check-transfer requires --baseline-dir and --review-pass")
    inventory = ladder.load_source_inventory()
    manifest, groups = prepare(inventory=inventory)
    pin = DIRECTORY / "source-manifest.json"
    if (pin.exists() or args.action in {"check", "inspect", "queue"}) and ladder.read_json(pin) != manifest:
        raise ValueError("Novel-1500 source selection drifted from its frozen anchors")
    if args.action in {"inspect", "queue", "check", "check-transfer"}:
        repairs = read_repairs(manifest)
    if args.action == "check-transfer":
        result = check_transfer(groups, repairs, args.review_pass, args.baseline_dir, args.out_dir)
        print("NOVEL1500_TRANSFER", json.dumps(result, ensure_ascii=False), flush=True)
        return
    if args.action == "queue":
        print(json.dumps(current_queue(manifest, repairs), ensure_ascii=False, indent=2))
        return
    if args.action == "inspect":
        index = args.index
        if index is None:
            queue = current_queue(manifest, repairs)
            if not queue["unresolved"]:
                print("No incomplete candidates.")
                return
            index = queue["unresolved"][0]["index"]
        description = inspect_case(index, groups, inventory[1], args.out_dir)
        if index in repairs:
            description["verified_signature"] = repairs[index]["after"]
        print(json.dumps(description, ensure_ascii=False, indent=2))
        return
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.action == "plan":
        ladder.write_json(args.out_dir / "source-manifest.json", manifest)
        return
    selected = groups if args.group is None else {args.group: groups[args.group]}
    if args.action == "replay":
        replay(selected, args.wordnet_dir, args.out_dir)
        return
    for end, group in selected.items():
        result, _ = checked_observation(end, group, args.out_dir)
        filename = f"novel-{end}-initial.json"
        if args.action == "check":
            check_result(end, group[0], expected_result(end, group[0], repairs), result)
        else:
            ladder.write_json(args.out_dir / filename, result)
        print(f"Novel-{end}: {result['counts']} (parse coverage, not semantic review)")
    if args.action == "snapshot":
        ladder.write_json(args.out_dir / "source-manifest.json", manifest)
        ladder.write_json(args.out_dir / "repair-queue.json",
                          repair_queue(manifest, selected, args.out_dir))


if __name__ == "__main__":
    main()
