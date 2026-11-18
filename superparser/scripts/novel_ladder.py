"""Freeze and replay additive 100-case novel cohorts through the corpus gateway."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import signal

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from scripts.audit_context_dependencies import fingerprint
from scripts.corpus_samples import BANDS
from scripts.diagnose_novel_parses import EXPECTED_500_COHORT_SHA256, select_cases
from scripts.evaluate_novel_transfer import (
    KBEST_WORK_LIMIT, MAX_ITEMS, DEADLINE_SECONDS, ROOT, _deadline, measure,
    normalized_identity, verify_source,
)
from seman_parser.engine import Parser, ParserResources

LADDER = ROOT / "research" / "novel_ladder"
SEMANTIC_DEFECTS = ROOT / "research" / "semantic_quality" / "confirmed_selected_defects.json"
FIRST = 501
SIZE = 100
SCHEMA = "seman2-novel-ladder-cohort-v1"
REVIEW_SCHEMA = "seman2-novel-ladder-review-v1"
LIMITS = {"chart_items": MAX_ITEMS, "kbest_work": KBEST_WORK_LIMIT,
          "seconds_per_case": DEADLINE_SECONDS}


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_id(case):
    return (case["book_id"], case["structural_paragraph_index"])


def source_key(case):
    return normalized_identity(case["source_text"])


def case_hash(case):
    return sha256(case["source_text"].encode()).hexdigest()


def pick(rows_by_book, excluded_paragraphs, excluded_texts, first):
    """Take 25 per book and per band, one paragraph and text identity per case.

    No parsing or grammar output is consulted. Rotate the extra slot to give
    each band and book exactly 25 of the 100 cases.
    """
    paragraphs = set(excluded_paragraphs)
    texts = set(excluded_texts)
    chosen = []
    if len(rows_by_book) != 4:
        raise ValueError("The selection policy requires the four pinned novel editions")
    for book_offset, (book_id, rows) in enumerate(sorted(rows_by_book.items())):
        for band_offset, (band, lo, hi) in enumerate(BANDS):
            quota = 6 + (book_offset == band_offset)
            taken = 0
            pool = [case for case in rows if lo <= case["tokens"] <= hi]
            pool.sort(key=lambda c: (
                digest(["novel-ladder-selection-v1", first, book_id,
                        c["structural_core_source_span"][0]]),
                c["structural_core_source_span"][0],
            ))
            for case in pool:
                para, key = source_id(case), source_key(case)
                if para in paragraphs or key in texts:
                    continue
                paragraphs.add(para)
                texts.add(key)
                index = first + len(chosen)
                chosen.append((index, band, case))
                taken += 1
                if taken == quota:
                    break
            if taken != quota:
                raise ValueError(f"Not enough independent paragraphs for {book_id} in {band}")
    if len(chosen) != SIZE:
        raise AssertionError("A rung must contain exactly 100 new cases")
    return chosen


def load_sources():
    cases, _ = select_cases(500)
    if fingerprint(cases) != EXPECTED_500_COHORT_SHA256:
        raise ValueError("The inherited Novel-500 source identity changed")
    books = {book.ebook_id: book for book in TRAIN_BOOKS}
    rows, bodies, editions = {}, {}, []
    for record in sorted(read_manifest()["books"], key=lambda item: item["ebook_id"]):
        book = books[record["ebook_id"]]
        body, info = load_cleaned(book)
        bodies[book.ebook_id] = body
        rows[book.ebook_id], _ = extract(book, body, length_min=4, length_max=32)
        editions.append({"book_id": book.ebook_id, "sha256": info["sha256"]})
    return cases, rows, bodies, editions


def anchor(index, band, case):
    return [index, case["book_id"], case["structural_paragraph_index"],
            *case["structural_core_source_span"], band, case_hash(case)]


def resolve(manifest, first, sources):
    _, rows, bodies, editions = sources
    if (manifest.get("schema") != SCHEMA or manifest.get("first_index") != first
            or manifest.get("legacy_cohort_sha256") != EXPECTED_500_COHORT_SHA256
            or manifest.get("editions") != editions):
        raise ValueError("Incompatible Novel Ladder cohort or source editions")
    anchors = manifest["anchors"]
    if ([a[0] for a in anchors] != list(range(first, first + SIZE))
            or manifest["cohort_sha256"] != digest(anchors)):
        raise ValueError("Novel Ladder ordered anchors do not match their pin")
    by_span = {(book_id, *c["structural_core_source_span"]): c
               for book_id, group in rows.items() for c in group}
    result = []
    for index, book_id, paragraph, start, stop, band, expected in anchors:
        case = by_span.get((book_id, start, stop))
        expected_band = next((b for b, lo, hi in BANDS if case and lo <= case["tokens"] <= hi), None)
        if (case is None or case_hash(case) != expected or source_id(case) != (book_id, paragraph)
                or band != expected_band):
            raise ValueError(f"Frozen Novel Ladder source no longer resolves: {index}")
        resolved = {**case, "ladder_index": index, "transfer_id": f"N{index}", "band": band}
        verify_source(resolved, bodies[book_id])
        result.append(resolved)
    return result


def case_files(directory):
    return sorted(directory.glob("novel-*-cohort.json"),
                  key=lambda path: int(path.name.split("-")[1]))


def read_ladder(directory, sources):
    cases, _, _, _ = sources
    paragraphs = {source_id(c) for c in cases}
    texts = {source_key(c) for c in cases}
    cohorts = []
    for i, path in enumerate(case_files(directory)):
        first = FIRST + SIZE * i
        if path.name != f"novel-{first + SIZE - 1}-cohort.json":
            raise ValueError(f"Unexpected or nonconsecutive cohort: {path}")
        manifest = read_json(path)
        resolved = resolve(manifest, first, sources)
        for case in resolved:
            para, key = source_id(case), source_key(case)
            if para in paragraphs or key in texts:
                raise ValueError(f"Overlapping prior source at {case['ladder_index']}")
            paragraphs.add(para)
            texts.add(key)
        cohorts.append((manifest, resolved))
    return cohorts, paragraphs, texts


def freeze(directory, sources):
    cohorts, paras, texts = read_ladder(directory, sources)
    for prior, cases in cohorts:
        end = cases[-1]["ladder_index"]
        marker = directory / f"novel-{end}-accepted.json"
        if not marker.exists():
            raise ValueError(f"Novel-{end} must be complete and reviewed before expanding")
        accepted = read_json(marker)
        accepted_cases(accepted, prior, end, load_review(directory, end, prior, accepted))
    first = FIRST + len(cohorts) * SIZE
    entries = [anchor(i, band, case) for i, band, case in pick(sources[1], paras, texts, first)]
    manifest = {"schema": SCHEMA, "first_index": first,
                "legacy_cohort_sha256": EXPECTED_500_COHORT_SHA256,
                "editions": sources[3], "cohort_sha256": digest(entries), "anchors": entries}
    resolve(manifest, first, sources)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"novel-{first + SIZE - 1}-cohort.json"
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return path


def graph_digest(package):
    """Fingerprint selected relations without process-local node IDs."""
    graph = package["graph"]
    identifiers = {n["id"]: i for i, n in enumerate(graph["nodes"])}
    nodes = [{k: v for k, v in node.items() if k != "id"} for node in graph["nodes"]]
    edges = [{**edge, "source": identifiers[edge["source"]],
              "target": identifiers[edge["target"]]} for edge in graph["relations"]]
    handles = {key: identifiers[value] for key, value in package["handles"].items()}
    return digest({"nodes": nodes, "relations": edges, "handles": handles})


def signatures(rows):
    return [{"index": r["ladder_index"], "status": r["status"],
             "forest_budget_exceeded": bool(r.get("forest_budget_exceeded")),
             "kbest_budget_exceeded": bool(r.get("kbest_budget_exceeded")),
             "root_rule": r.get("root_rule"),
             "rank_one_sha256": digest(r["tree"]) if r.get("tree") else None,
             "selected_graph_sha256": graph_digest(r["selected_graph"])
             if r.get("selected_graph") else None}
            for r in rows]


def result_cases(result, cohort, end):
    rows = result["cases"]
    if (result.get("schema") != "seman2-novel-ladder-result-v1"
            or result.get("cohort_sha256") != cohort["cohort_sha256"]
            or result.get("limits") != LIMITS
            or [r["index"] for r in rows] != list(range(end - SIZE + 1, end + 1))
            or result.get("counts") != dict(Counter(r["status"] for r in rows))):
        raise ValueError(f"Novel-{end} result identity, limits or counts differ from its pin")
    if any((r["status"] == "complete") != bool(r["rank_one_sha256"]) for r in rows):
        raise ValueError(f"Novel-{end} result contains an inconsistent selected-tree digest")
    if any("selected_graph_sha256" in r and (
        (r["status"] == "complete") != bool(r["selected_graph_sha256"])
    ) for r in rows):
        raise ValueError(f"Novel-{end} result contains an inconsistent selected-graph digest")
    return {r["index"]: r for r in rows}


def compare_rows(reference, observed, *, sealed=False):
    regressions = []
    for i, before in reference.items():
        after = observed[i]
        if before["status"] == "complete" and after["status"] != "complete":
            regressions.append((i, "lost complete parse"))
        elif before["status"] == "complete" and (
            before["rank_one_sha256"] != after["rank_one_sha256"]
        ):
            regressions.append((i, "selected tree changed"))
        for budget in ("forest_budget_exceeded", "kbest_budget_exceeded"):
            if not before[budget] and after[budget]:
                regressions.append((i, f"new {budget}"))
        if after["status"] == "error":
            regressions.append((i, "execution error"))
        if sealed and after != before and not any(r[0] == i for r in regressions):
            regressions.append((i, "accepted signature changed"))
    return regressions


def load_review(directory, end, cohort, result):
    rows = result_cases(result, cohort, end)
    path = directory / f"novel-{end}-review.json"
    doc = read_json(path) if path.exists() else {"schema": REVIEW_SCHEMA,
           "cohort_sha256": cohort["cohort_sha256"], "cases": []}
    if doc.get("schema") != REVIEW_SCHEMA or doc.get("cohort_sha256") != cohort["cohort_sha256"]:
        raise ValueError(f"Novel-{end} review identity differs from its cohort")
    review = {}
    for entry in doc["cases"]:
        index = entry["index"]
        observed = rows.get(index)
        if (not observed or index in review or entry["verdict"] not in ("verified", "needs_fix")
                or not isinstance(entry.get("evidence"), str) or not entry["evidence"].strip()):
            raise ValueError(f"Invalid Novel-{end} review entry {index}")
        for signature in ("rank_one_sha256", "selected_graph_sha256"):
            if entry.get(signature) != observed.get(signature):
                raise ValueError(f"Stale Novel-{end} review for N{index}: {signature} changed")
            if entry["verdict"] == "verified" and not re.fullmatch(r"[0-9a-f]{64}", entry.get(signature) or ""):
                raise ValueError(f"Cannot verify N{index} without a selected tree and graph")
        if entry["verdict"] == "verified" and observed["status"] != "complete":
            raise ValueError(f"Cannot verify an incomplete parse for N{index}")
        review[index] = entry
    return review


def known_semantic_defects(end):
    """Unresolved source-selected errors; do not confuse review with coverage."""
    if end < 700 or not SEMANTIC_DEFECTS.exists():
        return {}
    ledger = read_json(SEMANTIC_DEFECTS)
    if ledger.get("schema") != "seman2-selected-semantic-defect-ledger-v1":
        raise ValueError("Unrecognized selected semantic defect ledger")
    defect_map = {}
    for item in ledger.get("cases", []):
        index = item["index"]
        if end - SIZE < index <= end:
            if index in defect_map or item.get("status") != "needs_fix":
                raise ValueError(f"Malformed unresolved semantic defect N{index}")
            defect_map[index] = item
    return defect_map


def accepted_cases(result, cohort, end, review):
    rows = result_cases(result, cohort, end)
    if (any(r["status"] != "complete" for r in rows.values())
            or {i for i, r in review.items() if r["verdict"] == "verified"} != set(rows)):
        raise ValueError(f"Novel-{end} must be complete and reviewed before expanding")
    # Recognition and an individually written review verdict are necessary,
    # but a known false selected attachment invalidates that certification.
    # Fail closed: changing the tree's hash does NOT automatically clear a
    # recorded fault; remove a defect only after source-backed controls pass.
    unresolved = sorted(known_semantic_defects(end))
    if unresolved:
        raise ValueError(
            f"Novel-{end} semantic acceptance blocked by "
            f"{len(unresolved)} outstanding selected-tree defects: {unresolved}"
        )
    return rows


def check(cohorts, directory, out_dir):
    failures = []
    for cohort, cases in cohorts:
        end = cases[-1]["ladder_index"]
        prefix = f"novel-{end}"
        accepted = directory / f"{prefix}-accepted.json"
        current = directory / f"{prefix}-current.json"
        reference = accepted if accepted.exists() else current
        baseline = read_json(directory / f"{prefix}-initial.json")
        reference_data = read_json(reference)
        result_cases(baseline, cohort, end)
        review = load_review(directory, end, cohort, reference_data)
        pin = (accepted_cases(reference_data, cohort, end, review) if accepted.exists()
               else result_cases(reference_data, cohort, end))
        candidate_data = read_json(out_dir / f"{prefix}-result.json")
        candidate = result_cases(candidate_data, cohort, end)
        errors = compare_rows(pin, candidate, sealed=accepted.exists())
        failures.extend(errors)
        if not errors:
            load_review(directory, end, cohort, candidate_data)
        print_quality(prefix, candidate, review)
        print(f"{prefix} coverage diagnostics: initial {baseline['counts']}; current "
              f"{dict(Counter(r['status'] for r in candidate.values()))}", flush=True)
    if failures:
        raise ValueError(f"Novel Ladder regressions: {failures}")


def print_quality(prefix, rows, review):
    end = int(prefix.rsplit("-", 1)[1])
    known = known_semantic_defects(end)
    # Known errors always override a legacy 'verified' entry (N660).
    verdicts = {
        index: ("needs_fix" if index in known else
                review[index]["verdict"] if index in review else "unreviewed")
        for index in rows
    }
    verified = sum(v == "verified" for v in verdicts.values())
    needs_fix = sum(v == "needs_fix" for v in verdicts.values())
    unreviewed = sum(v == "unreviewed" for v in verdicts.values())
    print(f"{prefix} quality: {verified}/{len(rows)} verified; {needs_fix} need a fix; "
          f"{unreviewed} unreviewed", flush=True)


def quality(cohorts, directory):
    for cohort, cases in cohorts:
        end = cases[-1]["ladder_index"]
        prefix = f"novel-{end}"
        accepted = directory / f"{prefix}-accepted.json"
        data = read_json(accepted if accepted.exists() else directory / f"{prefix}-current.json")
        review = load_review(directory, end, cohort, data)
        rows = accepted_cases(data, cohort, end, review) if accepted.exists() else result_cases(data, cohort, end)
        print_quality(prefix, rows, review)


def print_queue(cohorts, directory, after):
    for cohort, cases in cohorts:
        end = cases[-1]["ladder_index"]
        accepted = directory / f"novel-{end}-accepted.json"
        if accepted.exists():
            data = read_json(accepted)
            accepted_cases(data, cohort, end, load_review(directory, end, cohort, data))
            continue
        reference = read_json(directory / f"novel-{end}-current.json")
        rows = result_cases(reference, cohort, end)
        reviewed = load_review(directory, end, cohort, reference)
        audit = {int(i): reason for i, reason in reference.get("rank_one_review_queue", {}).items()}
        audit.update({i: r["evidence"] for i, r in reviewed.items() if r["verdict"] == "needs_fix"})
        known = known_semantic_defects(end)
        audit.update({i: r["observed_defect"] for i, r in known.items()})
        unreviewed = [r for i, r in rows.items() if i not in reviewed]
        eligible = [r for r in unreviewed if r["status"] != "complete"]
        if not eligible and audit:
            eligible = [r for i, r in rows.items()
                        if i in audit and (i in known or
                        reviewed.get(i, {}).get("verdict") != "verified")]
        if not eligible:
            eligible = unreviewed
        if not eligible:
            print(f"Novel-{end}: all selected analyses verified; save the accepted pin before expansion.")
            return
        next_row = next((r for r in eligible if r["index"] > after), eligible[0])
        case = cases[next_row["index"] - cohort["first_index"]]
        review = {"review_reason": audit[next_row["index"]]} if next_row["index"] in audit else {}
        print(json.dumps({**next_row, **review, "source_text": case["source_text"],
                          "book_id": case["book_id"],
                          "source_span": case["structural_core_source_span"]}, ensure_ascii=False))
        return
    print("Every recorded cohort is accepted.")


def compare_legacy(diagnostics, baseline):
    """Keep the canonical 500 results unmodified, including selected trees."""
    rows = [json.loads(s) for s in diagnostics.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 500 or [r["index"] for r in rows] != list(range(500)):
        raise ValueError("Expected all 500 historical diagnostic rows in order")
    legacy = [[r["index"], r["book_id"], r["ordinal"], r["sha256"], r["status"],
               bool(r.get("forest_budget_exceeded")), bool(r.get("kbest_budget_exceeded")),
               r.get("rank_one_sha256")] for r in rows]
    observed = sha256("".join(json.dumps(r) + "\n" for r in legacy).encode()).hexdigest()
    if observed != baseline:
        raise ValueError(f"Novel-500 regression fingerprint changed: {observed}")


def run(cohorts, wordnet_dir, out_dir):
    parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir),
                    cache_size=0, max_items=MAX_ITEMS)
    parser.parse("John opened the box.")
    out_dir.mkdir(parents=True, exist_ok=True)
    previous = signal.signal(signal.SIGALRM, _deadline)
    try:
        for cohort, cases in cohorts:
            end = cases[-1]["ladder_index"]
            rows = []
            with (out_dir / f"novel-{end}-parses.jsonl").open("w", buffering=1, encoding="utf-8") as out:
                for case in cases:
                    row = {**case, **measure(parser, case, with_semantics=True)}
                    rows.append(row)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
            counts = dict(sorted(Counter(r["status"] for r in rows).items()))
            result = {"schema": "seman2-novel-ladder-result-v1",
                      "cohort_sha256": cohort["cohort_sha256"],
                      "limits": LIMITS,
                      "counts": counts, "cases": signatures(rows)}
            write_json(out_dir / f"novel-{end}-result.json", result)
            print(f"Novel-{end}: {counts}", flush=True)
    finally:
        signal.signal(signal.SIGALRM, previous)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ladder-dir", type=Path, default=LADDER)
    actions = cli.add_subparsers(dest="action", required=True)
    actions.add_parser("freeze")
    replay = actions.add_parser("run")
    replay.add_argument("--wordnet-dir", type=Path, required=True)
    replay.add_argument("--out-dir", type=Path, required=True)
    verify = actions.add_parser("check")
    verify.add_argument("--out-dir", type=Path, required=True)
    verify.add_argument("--legacy-diagnostics", type=Path)
    queue = actions.add_parser("next")
    queue.add_argument("--after", type=int, default=FIRST - 1)
    actions.add_parser("quality")
    args = cli.parse_args()
    sources = load_sources()
    if args.action == "freeze":
        print(freeze(args.ladder_dir, sources))
        return
    cohorts, _, _ = read_ladder(args.ladder_dir, sources)
    if not cohorts:
        cli.error("No pinned ladder cohorts")
    if args.action == "next":
        print_queue(cohorts, args.ladder_dir, args.after)
    elif args.action == "quality":
        quality(cohorts, args.ladder_dir)
    elif args.action == "run":
        run(cohorts, args.wordnet_dir, args.out_dir)
    else:
        check(cohorts, args.ladder_dir, args.out_dir)
        if args.legacy_diagnostics:
            compare_legacy(args.legacy_diagnostics, read_json(
                args.ladder_dir / "novel-500-protected.json",
            )["rank_one_run_sha256"])


if __name__ == "__main__":
    main()
