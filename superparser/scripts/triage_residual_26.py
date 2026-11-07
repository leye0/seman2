"""Reproducible research queue for the 26 residuals of the frozen 500-case cohort.

No parsing or linguistic repair happens here.  This is an observational audit:
actual canonical recognition outcomes and original-source context are kept
separate from human hypotheses about their linguistic causes.  A tracked
case remains in the register after it becomes complete.  Newly failing
cases are surfaced rather than silently changing the original denominator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "seman2-residual-research-triage-v1"
CONCLUSIVE = frozenset({"no_structural_root", "roots_without_valid_analysis"})
CENSORED = frozenset({"timeout", "forest_budget_exceeded", "kbest_budget_exceeded", "both_budgets_exceeded"})
TRACKS = frozenset({
    "contextual_fragment", "dialogue_structure", "finite_syntax",
    "discourse_construction", "notation_or_genre", "resource_limit",
    "marked_agreement",
})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
            if line.strip()]


def outcome(status: str) -> str:
    if status == "complete":
        return "complete"
    if status in CONCLUSIVE:
        return "structural_unresolved"
    if status in CENSORED:
        return "resource_censored"
    if status == "error":
        return "execution_error"
    raise ValueError(f"Unrecognized canonical status {status!r}")


def _verified_rows(rows: list[Mapping[str, Any]], size: int, kind: str) -> dict[int, Mapping[str, Any]]:
    if len(rows) != size:
        raise ValueError(f"{kind}: expected {size} rows, found {len(rows)}")
    indexed = {row["index"]: row for row in rows}
    if sorted(indexed) != list(range(size)):
        raise ValueError(f"{kind}: duplicate, missing or out-of-order cohort indices")
    if [row["index"] for row in rows] != list(range(size)):
        raise ValueError(f"{kind}: row order differs from canonical cohort")
    return indexed


def triage(
    diagnostics: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
    failed: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Join observed results to immutable case IDs; never infer grammatical faults."""
    size = int(reference["cohort_size"])
    digest = reference["cohort_sha256"]
    if summary["cohort_sha256"] != digest:
        raise ValueError("Frozen cohort checksum mismatch")
    d_by_index = _verified_rows(diagnostics, size, "diagnostics")
    c_by_index = _verified_rows(contexts, size, "contexts")
    if (len(failed) != len({row["index"] for row in failed}) or
            any(row["index"] not in d_by_index for row in failed)):
        raise ValueError("Invalid or duplicate failed cases")
    f_by_index = {row["index"]: row for row in failed}
    actual_failed = {i for i, row in d_by_index.items() if row["status"] != "complete"}
    if set(f_by_index) != actual_failed:
        raise ValueError("Failed-only diagnostics do not match the canonical run")
    for i in range(size):
        d, ctx = d_by_index[i], c_by_index[i]
        if (d["status"] != ctx["status"] or
                d["source_text"] != ctx["source_text"] or
                d["book_id"] != ctx["book_id"] or
                d["source_text"] != ctx["context"]["source_text"]):
            raise ValueError(f"Inconsistent provenance/status at index {i}")
        if i in f_by_index and f_by_index[i]["case_id"] != d["case_id"]:
            raise ValueError(f"Failed-case identity mismatch at {i}")
    frozen = reference["cases"]
    if len(frozen) != 26 or len({r["index"] for r in frozen}) != 26:
        raise ValueError("Reference must contain the 26 unique original cases")
    ref_by_index = {row["index"]: row for row in frozen}
    for index, pinned in ref_by_index.items():
        actual = d_by_index[index]
        if (pinned["case_id"] != actual["case_id"] or
                pinned["baseline_status"] == "complete" or
                pinned["baseline_status"] not in CONCLUSIVE | CENSORED):
            raise ValueError(f"Baseline case identity/status mismatch at {index}")
        tracks = pinned["research_tracks"]
        if (not tracks or len(tracks) != len(set(tracks)) or
                not set(tracks) <= TRACKS):
            raise ValueError(f"Invalid research tracks at {index}")
        if pinned["assessment"] not in {"provisional_hypothesis", "verified_marked_mode_prior_test"}:
            raise ValueError(f"Invalid assessment provenance at {index}")
        if (pinned["assessment"] == "verified_marked_mode_prior_test" and
                ("marked_agreement" not in tracks or not pinned.get("test_reference"))):
            raise ValueError(f"Marked agreement needs pinned test provenance at {index}")

    rows: list[dict[str, Any]] = []
    for index in sorted(set(ref_by_index) | actual_failed):
        observed = d_by_index[index]
        ctx = c_by_index[index]
        prior = ref_by_index.get(index)
        status = observed["status"]
        evidence = f_by_index.get(index, {}).get("lexical_diagnostic")
        lexical = None if evidence is None else {
            "words_without_any_candidate": evidence["words_without_any_candidate"],
            "words_without_exact_candidate": evidence["words_without_exact_candidate"],
            "candidate_count": evidence["lexical_candidate_count"],
        }
        row = {
            "index": index,
            "case_id": observed["case_id"],
            "book_id": observed["book_id"],
            "source_text": observed["source_text"],
            "analysis_text": observed["canonical_analysis_text"],
            "original_26_member": prior is not None,
            "baseline_status": prior["baseline_status"] if prior else None,
            "current_status": status,
            "current_outcome": outcome(status),
            "trajectory": ("new_unreviewed_failure" if prior is None else
                           "recovered" if status == "complete" else "unresolved"),
            "research_tracks": list(prior["research_tracks"]) if prior else [],
            "hypothesis": prior["hypothesis"] if prior else None,
            "hypothesis_assessment": prior["assessment"] if prior else "unreviewed",
            "test_reference": prior.get("test_reference") if prior else None,
            "marked_parse_reexecuted_in_this_audit": False,
            "observed_evidence": {
                "structural_root_nodes": observed.get("structural_root_nodes"),
                "forest_budget_exceeded": bool(observed.get("forest_budget_exceeded")),
                "kbest_budget_exceeded": bool(observed.get("kbest_budget_exceeded")),
                "dialogue_scoped": bool(observed.get("dialogue_scoped")),
                "context_signals": ctx["surface_signals"],
                "source_context": {
                    "semicolon_part_index": ctx["context"]["semicolon_part_index"],
                    "semicolon_parts": ctx["context"]["semicolon_parts"],
                    "preceding_semicolon_part": ctx["context"]["preceding_semicolon_part"],
                    "full_unsplit_sentence": ctx["context"]["full_unsplit_sentence"],
                },
                "lexical_diagnostic": lexical,
            },
            "grammatical_fault_established_by_this_audit": False,
        }
        rows.append(row)

    original = [x for x in rows if x["original_26_member"]]
    unresolved = [x for x in original if x["trajectory"] == "unresolved"]
    current = [x for x in rows if x["current_status"] != "complete"]
    tracks = Counter(track for x in unresolved for track in x["research_tracks"])
    summary_out = {
        "schema": SCHEMA,
        "cohort_sha256": digest,
        "cohort_size": size,
        "original_residuals": 26,
        "original_still_unresolved": len(unresolved),
        "original_recovered": 26 - len(unresolved),
        "new_unreviewed_failures": len([x for x in rows if x["trajectory"] == "new_unreviewed_failure"]),
        "current_total_failed": len(current),
        "current_status_counts": dict(sorted(Counter(x["current_status"] for x in current).items())),
        "original_track_counts_overlapping": dict(sorted(tracks.items())),
        "current_failed_with_lexical_diagnostic": sum(x["observed_evidence"]["lexical_diagnostic"] is not None for x in current),
        "current_failed_without_full_lexical_candidate": sum(
            bool(x["observed_evidence"]["lexical_diagnostic"] and
                 x["observed_evidence"]["lexical_diagnostic"]["words_without_any_candidate"])
            for x in current
        ),
        "interpretation": (
            "Recognition failure does not imply grammatical anomaly. Tracks and surface/context "
            "signals are research hypotheses, not verified root causes or gold labels. "
            "Marked-mode evidence links to pre-existing tests but is not rerun by this audit. "
            "Resource-censored cases are not conclusive grammatical failures."
        ),
    }
    return rows, summary_out


def render_overview(rows: list[dict[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# Frozen 26-case residual research register",
        "",
        f"Cohort SHA-256: `{summary['cohort_sha256']}`. This is an **observational** research register,",
        "not a list of 26 proven grammar errors. Recovered historical cases remain visible.",
        "",
        f"Original unresolved: **{summary['original_still_unresolved']}/26**; original recovered: "
        f"**{summary['original_recovered']}**; new failures: **{summary['new_unreviewed_failures']}**.",
        "",
        "| Index | Current outcome | Research tracks (hypotheses) |", "|---:|---|---|",
    ]
    for row in rows:
        tracks = ", ".join(row["research_tracks"]) or "NEW: unreviewed"
        lines.append(f"| {row['index']} | {row['current_status']} | {tracks} |")
    lines += ["", "## Case-by-case notes", ""]
    for row in rows:
        lines.extend([
            f"### {row['index']} — {row['case_id']}", "",
            f"Observed: `{row['current_status']}`; original: `{row['baseline_status']}`; "
            f"progress: `{row['trajectory']}`.", "",
            "> " + row["source_text"].replace("\n", " "), "",
            f"Research hypothesis (**{row['hypothesis_assessment']}**): {row['hypothesis'] or 'Not reviewed'}", "",
            "Context signals (observed, not grammar labels): " + 
            (", ".join(row["observed_evidence"]["context_signals"]) or "none") + ".", "",
        ])
        before = row["observed_evidence"]["source_context"]["preceding_semicolon_part"]
        if before:
            lines.extend(["Preceding part of the same original sentence:", "", "> " + before.replace("\n", " "), ""])
        lex = row["observed_evidence"]["lexical_diagnostic"]
        if lex is None:
            lines.extend(["Full lexical diagnostic: **not available** (e.g. timed out or recovered).", ""])
        else:
            lines.extend(["Words with no full lexical candidate: `" +
                          repr(lex["words_without_any_candidate"]) + "`.", ""])
        if row["test_reference"]:
            lines.extend([f"Existing independently executed regression test: `{row['test_reference']}`.", ""])
    lines += ["## Validation semantics", "",
              "- An observed semicolon or quote transfer does **not** prove an ellipse or an error.",
              "- A completed analysis is not itself proof of a valid selected attachment.",
              "- Marked usage is not automatically an author error or a dialect attribution.",
              "- Resource exhaustion is censoring, not negative grammatical evidence.",
              "- No parser, corpus text, budget, ranking, grammar or lexicon is changed by this audit.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("diagnostics", "contexts", "failed", "summary", "reference", "out_dir"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    rows, overview = triage(
        read_jsonl(args.diagnostics), read_jsonl(args.contexts),
        read_jsonl(args.failed), json.loads(args.summary.read_text(encoding="utf8")),
        json.loads(args.reference.read_text(encoding="utf8")),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "residual_research_cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf8",
    )
    (args.out_dir / "residual_research_summary.json").write_text(
        json.dumps(overview, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "residual_research_overview.md").write_text(
        render_overview(rows, overview), encoding="utf8",
    )
    print("RESIDUAL_RESEARCH_SUMMARY", json.dumps(overview, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

