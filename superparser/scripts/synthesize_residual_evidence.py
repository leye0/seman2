"""Join the frozen residual ledger with independent, non-causal diagnostics.

This is a reporting step AFTER the canonical 500 parses, not another parser.
Every observation keeps its case identity, source and analysis distinction,
and evidence limitations. In particular, local failed derivations are never
promoted into a sentence-level grammatical error or a unique failure cause.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "seman2-residual-evidence-synthesis-v1"
TRACE_SCOPES = ("scoped_dialogue", "ordinary_fallback")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()
            if line.strip()]


def _indexed(rows: list[Mapping[str, Any]], name: str) -> dict[int, Mapping[str, Any]]:
    indexed: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        index = row.get("index")
        if type(index) is not int or index in indexed:
            raise ValueError(f"{name}: missing, invalid or repeated index {index!r}")
        indexed[index] = row
    return indexed


def _identity(source: Mapping[str, Any], other: Mapping[str, Any], name: str) -> None:
    if (source["index"] != other["index"] or
            source["case_id"] != other["case_id"]):
        raise ValueError(f"{name}: case identity mismatch at {source['index']}")


def _trace_view(trace: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(trace, dict):
        return None
    if trace.get("exhaustive") is not False or trace.get("grammatical_fault_established") is not False:
        raise ValueError("Rejection traces must explicitly disclaim exhaustive or fault proof")
    events = trace.get("events", [])
    if not isinstance(events, list):
        raise ValueError("Trace events must be a list")
    if (trace.get("sampled_events") != len(events) or
            not isinstance(trace.get("observed_events"), int) or
            trace["observed_events"] < len(events) or
            bool(trace.get("truncated")) != (trace["observed_events"] > len(events))):
        raise ValueError("Inconsistent bounded rejection sample metadata")
    priority = [e for e in events if e.get("stage", "").startswith("positive_evidence_")
                or e.get("stage") == "child_context_exhausted"]
    # Retain only a few already sampled local events; this is neither a
    # representative sample nor a proof that a complete tree is impossible.
    examples = []
    for event in (priority + [e for e in events if e not in priority])[:5]:
        exact = event.get("reference_span_mapping") == "exact"
        if exact and (not isinstance(event.get("reference_span"), list)
                      or len(event["reference_span"]) != 2):
            raise ValueError("Exact source mapping requires an actual two-ended span")
        examples.append({
            "stage": event["stage"],
            "rule_id": event.get("rule_id"),
            "category": event.get("category"),
            "analysis_span": event.get("analysis_span"),
            "reference_span": event.get("reference_span") if exact else None,
            "reference_mapping": "exact" if exact else "unavailable",
            "candidate_atom_conflicts": event.get("direct_atom_conflicts", []),
            "required_positive_features": event.get("required_positive_features", []),
        })
    local = trace.get("validated_local_constituents")
    local_view = None
    if local is not None:
        if (local.get("schema") != "seman2-local-constituent-proof-sample-v1" or
                local.get("exhaustive") is not False or
                local.get("global_tree_proven") is not False or
                local.get("sentence_grammatical_fault_established") is not False):
            raise ValueError("Local constituent witness provenance or limits invalid")
        witnesses = local.get("witnesses", [])
        if (not isinstance(witnesses, list) or
                local.get("sampled_local_constituents") != len(witnesses) or
                local.get("observed_materialized_rule_analyses", -1) < len(witnesses)):
            raise ValueError("Inconsistent successful constituent samples")
        if any(w.get("proof_basis") != "materialized_rule_after_context_unification"
               or w.get("global_tree_selected") is not False
               or w.get("whole_sentence_grammaticality_proven") is not False
               or not w.get("rule_id") or not w.get("children")
               or not set(w.get("required_positive_features", [])).issubset(
                   w.get("witnessed_positive_features", []))
               for w in witnesses):
            raise ValueError("A sampled constituent lacks a verified local proof contract")

        def source_span(frame):
            if frame.get("reference_span_mapping") != "exact":
                return None
            span = frame.get("reference_span")
            if not isinstance(span, list) or len(span) != 2:
                raise ValueError("Local constituent exact span has no source proof")
            return span

        local_view = {
            "observed_materialized_rule_analyses": local["observed_materialized_rule_analyses"],
            "sampled_local_constituents": len(witnesses),
            "sample_truncated": bool(local.get("truncated")),
            "witnesses": [{
                "proof_basis": w["proof_basis"],
                "rule_id": w["rule_id"],
                "category": w["category"],
                "analysis_span": w["analysis_span"],
                "source_span": source_span(w),
                "verified_features": w["verified_features"],
                "required_context_features": w["required_context_features"],
                "children": [{"category": child["category"],
                              "rule_id": child.get("rule_id"),
                              "analysis_span": child["analysis_span"],
                              "source_span": source_span(child)}
                             for child in w["children"]],
                "global_tree_selected": False,
                "sentence_grammaticality_proven": False,
            } for w in witnesses],
            "exhaustive": False,
            "sentence_grammatical_fault_established": False,
        }
    return {
        "observed_events": trace.get("observed_events"),
        "sampled_events": len(events),
        "sample_truncated": bool(trace.get("truncated")),
        "stages_in_retained_sample": dict(sorted(Counter(e["stage"] for e in events).items())),
        "local_atom_conflicts_in_retained_sample": sum(
            len(e.get("direct_atom_conflicts", [])) for e in events),
        "examples": examples,
        "validated_local_constituents": local_view,
        "exhaustive": False,
        "sentence_fault_proven": False,
        "failure_cause_proven": False,
    }


def synthesize(
    register: list[Mapping[str, Any]],
    register_summary: Mapping[str, Any],
    preflight: list[Mapping[str, Any]],
    lexical: list[Mapping[str, Any]],
    dialogue: list[Mapping[str, Any]],
    dialogue_summary: Mapping[str, Any],
    comparators: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fail closed on inconsistent sources; never reinterpret parser outcomes."""
    digest = register_summary["cohort_sha256"]
    if (digest != dialogue_summary.get("cohort_sha256") or
            register_summary.get("cohort_size") != 500 or
            register_summary.get("original_residuals") != 26):
        raise ValueError("Canonical cohort/probe identity mismatch")
    registered = _indexed(register, "register")
    if len([r for r in register if r["original_26_member"]]) != 26:
        raise ValueError("The 26 historical residuals must remain visible")
    pf = _indexed(preflight, "preflight")
    if len(pf) != 500 or set(pf) != set(range(500)):
        raise ValueError("Preflight must cover exactly the original 500 cases")
    lex = _indexed(lexical, "lexical")
    dial = _indexed(dialogue, "dialogue")
    comp = _indexed(comparators, "comparators")
    if (set(dial) != set(dialogue_summary["target_indices"]) or
            dialogue_summary["cases"] != len(dial)):
        raise ValueError("Dialogue target indices do not match replay summary")
    if set(comp) != {76, 244, 463, 480}:
        raise ValueError("Independent strict/marked controls are missing or replaced")
    if any(comp[i]["kind"] != ("marked_opt_in" if i in (463, 480)
                                 else "successful_strict_control") for i in comp):
        raise ValueError("Independent control roles were changed")
    for index, source in registered.items():
        _identity(source, pf[index], "preflight")
        if (source["current_status"] != pf[index]["canonical_status"] or
                source["source_text"] != pf[index]["source_text"]):
            raise ValueError(f"Canonical/preflight outcome mismatch at {index}")
    for name, items in (("lexical", lex), ("dialogue", dial), ("comparator", comp)):
        for index, row in items.items():
            source = registered.get(index) or pf.get(index)
            if source is None:
                raise ValueError(f"{name}: index outside cohort")
            _identity(source, row, name)
            if row["canonical_status"] != (source.get("current_status") or
                                           source.get("canonical_status")):
                raise ValueError(f"{name}: outcome mismatch at {index}")
            # These fields exist in the independently generated artifacts.
            # Reject a valid case ID attached to the wrong quotation projection.
            if ("analysis_text" in row and index in registered and
                    row["analysis_text"] != registered[index]["analysis_text"]):
                raise ValueError(f"{name}: analysis text mismatch at {index}")
            if ("source_text" in row and index in registered and
                    row["source_text"] != registered[index]["source_text"]):
                raise ValueError(f"{name}: source text mismatch at {index}")
    for index, row in dial.items():
        evidence = registered.get(index, {}).get("observed_evidence", {})
        scoped = evidence.get("dialogue_attempt") or {}
        if (index not in registered or
                registered[index]["current_status"] == "complete" or
                scoped.get("structural_root_nodes", 0) <= 0 or
                scoped["structural_root_nodes"] != row["canonical_dialogue_root_nodes"] or
                row.get("independent_replay") is not True):
            raise ValueError(f"Dialogue replay not eligible/independent at {index}")

    # Lexical spotchecks cover all *current* failures and sampled controls;
    # absence in a recovered case must not be interpreted as lexical absence.
    missing_failed = {i for i, row in registered.items()
                      if row["current_status"] != "complete"} - set(lex)
    if missing_failed:
        raise ValueError(f"Unobserved current failures in lexical audit: {sorted(missing_failed)}")

    rows = []
    for index in sorted(registered):
        source = registered[index]
        observed = source["observed_evidence"]
        surface = pf[index]["preflight"]
        lexical_row = lex.get(index)
        replay = dial.get(index)
        marked = comp.get(index) if index in (463, 480) else None
        if marked and marked["canonical_status"] == "complete":
            raise ValueError("Marked comparison silently substituted for strict outcome")
        context = observed["source_context"]
        checks = []
        if source["trajectory"] == "recovered":
            checks.append("verify_recovered_selected_tree_and_attachments")
        if source["current_outcome"] == "resource_censored":
            checks.append("investigate_budget_or_deadline_censoring")
        if context["semicolon_part_index"] > 0:
            checks.append("compare_source_continuation_with_independent_finite_clauses")
        if replay is not None:
            checks.append("inspect_scoped_dialogue_unification_and_validity")
        if marked is not None:
            checks.append("compare_strict_with_independent_marked_tree")
        if lexical_row and lexical_row["candidate_agreement_hypothesis"]:
            checks.append("inspect_candidate_agreement_with_actual_syntactic_links")
        if "notation_or_genre" in source["research_tracks"]:
            checks.append("inspect_register_or_notation_without_forcing_a_finite_clause")
        if (observed["lexical_diagnostic"] is not None and
                observed["lexical_diagnostic"]["words_without_any_candidate"]):
            checks.append("inspect_missing_lexical_candidates")
        # Semicolon and dialogue signals are never a substitute for examining
        # the finite syntax. In particular, residual #115 has overt subjects
        # despite being a continuation of its original source sentence.
        if source["current_outcome"] == "structural_unresolved":
            checks.append("inspect_constituents_valence_and_selected_attachments")
        traces = {}
        if replay:
            for name in TRACE_SCOPES:
                traces[name] = _trace_view((replay.get(name) or {}).get("rejection_trace"))
        if marked:
            for name, trace in marked.get("traces", {}).items():
                traces["marked_" + name] = _trace_view(trace)
        rows.append({
            "index": index,
            "case_id": source["case_id"],
            "book_id": source["book_id"],
            "source_text": source["source_text"],
            "analysis_text": source["analysis_text"],
            "original_26_member": source["original_26_member"],
            "canonical_status": source["current_status"],
            "canonical_outcome": source["current_outcome"],
            "trajectory": source["trajectory"],
            "research_tracks_are_hypotheses": source["research_tracks"],
            "research_hypothesis": source["hypothesis"],
            "hypothesis_assessment": source["hypothesis_assessment"],
            "prior_marked_test_reference": source["test_reference"],
            "source_context": context,
            "preflight": {
                "lane": surface["lane"],
                "surface_signals": surface["signals"],
                "not_a_grammatical_label": True,
            },
            "lexical_spotcheck": None if lexical_row is None else {
                "candidate_agreement_hypothesis": lexical_row["candidate_agreement_hypothesis"],
                "candidate_count": lexical_row["lexical_candidates"],
                "candidate_hypothesis_is_not_a_syntactic_relation": True,
            },
            "canonical_lexical_diagnostic": observed["lexical_diagnostic"],
            "dialogue_replay": None if replay is None else {
                "outcome": replay["replay_outcome"],
                "independent": True,
                "does_not_replace_canonical_status": True,
            },
            "marked_comparator": None if marked is None else {
                "outcome": marked["replay_outcome"],
                "selected_rule": marked.get("selected_rule"),
                "selected_deviation_count": marked.get("selected_usage_deviation_count"),
                "opt_in_only": True,
                "does_not_replace_canonical_status": True,
            },
            "sampled_local_rejection_evidence": traces,
            "suggested_checks_not_diagnoses": checks,
            "grammatical_fault_established": False,
            "unique_failure_cause_established": False,
            "exhaustive": False,
        })
    summary = {
        "schema": SCHEMA,
        "cohort_sha256": digest,
        "original_26_retained": 26,
        "current_cases_including_new_failures": len(rows),
        "current_unresolved": sum(r["canonical_status"] != "complete" for r in rows),
        "recovered_historical": sum(r["trajectory"] == "recovered" for r in rows),
        "new_unreviewed_failures": sum(r["trajectory"] == "new_unreviewed_failure" for r in rows),
        "scoped_dialogue_replays": len(dial),
        "marked_opt_in_comparisons": 2,
        "local_sample_events": sum(
            entry["sampled_events"] for row in rows
            for entry in row["sampled_local_rejection_evidence"].values()
            if entry is not None),
        "validated_local_constituents_sampled": sum(
            entry["validated_local_constituents"]["sampled_local_constituents"]
            for row in rows for entry in row["sampled_local_rejection_evidence"].values()
            if entry is not None and entry["validated_local_constituents"] is not None),
        "source_identity_validated": True,
        "no_causal_or_grammatical_fault_inference": True,
        "canonical_parse_not_reexecuted": True,
    }
    return rows, summary


def render(rows: list[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# Residual evidence synthesis — 26 historical cases and new failures", "",
        f"Frozen cohort SHA-256: `{summary['cohort_sha256']}`. All **26** historical",
        "identities are retained, even if a case is now complete. This report joins",
        "previously measured, independently identified evidence; it does not parse", 
        "again, diagnose authors' intentions, or infer mistakes from noncompletion.", "",
        "| Index | Strict outcome | Surface clues | Independent replay | Next checks (not diagnoses) |",
        "|---:|---|---|---|---|",
    ]
    for r in rows:
        surface = ", ".join(r["preflight"]["surface_signals"]) or "none"
        replay = r["dialogue_replay"]
        marked = r["marked_comparator"]
        paired = ("dialogue: " + replay["outcome"] if replay else "—")
        if marked:
            paired += "; marked opt-in: " + marked["outcome"]
        lines.append("| " + " | ".join((str(r["index"]), r["canonical_status"],
                        surface, paired, ", ".join(r["suggested_checks_not_diagnoses"]))) + " |")
    lines += ["", "## Local observations by case", ""]
    for r in rows:
        lines += [
            f"### #{r['index']} — `{r['case_id']}`", "",
            "> " + r["source_text"].replace("\n", " "), "",
            f"Strict: `{r['canonical_status']}`; trajectory: `{r['trajectory']}`. "
            "Surface/lexical clues are hypotheses, not dependencies.", "",
            f"Historical review ({r['hypothesis_assessment']}): "
            f"{r['research_hypothesis'] or 'unreviewed'}", "",
        ]
        before = r["source_context"].get("preceding_semicolon_part")
        if before:
            lines += ["Preceding source segment (not a proven grammatical dependency):", "",
                      "> " + before.replace("\n", " "), ""]
        lex = r["lexical_spotcheck"]
        lines.append("Lexical spotcheck: " + (
            f"{lex['candidate_count']} candidates; adjacent agreement hypothesis="
            f"{lex['candidate_agreement_hypothesis']}." if lex else "not sampled."))
        for scope, trace in r["sampled_local_rejection_evidence"].items():
            if trace is None:
                lines.append(f"- `{scope}`: no completed bounded trace")
            else:
                lines.append(f"- `{scope}`: {trace['sampled_events']} retained local events; "
                             f"{trace['local_atom_conflicts_in_retained_sample']} candidate atom conflicts; "
                             f"truncated={trace['sample_truncated']}; exhaustive=false")
                for event in trace["examples"]:
                    lines.append(f"  - `{event['stage']}` `{event['rule_id']}` "
                                 f"analysis {event['analysis_span']}; "
                                 f"source {event['reference_span'] if event['reference_mapping'] == 'exact' else 'unavailable'}")
                local = trace["validated_local_constituents"]
                if local is not None:
                    lines.append(
                        f"  - **Positive local proof samples**: "
                        f"{local['sampled_local_constituents']} retained, "
                        f"{local['observed_materialized_rule_analyses']} observed; "
                        "not full-sentence proofs")
                    for witness in local["witnesses"][:6]:
                        lines.append(
                            f"    - `{witness['category']}` via `{witness['rule_id']}` "
                            f"analysis {witness['analysis_span']}, "
                            f"source {witness['source_span'] if witness['source_span'] is not None else 'unavailable'} "
                            f"with {len(witness['children'])} locally validated children")
        lines.append("")
    lines += [
        "## Interpretation limits", "",
        "- A sampled unification rejection is local to one attempted derivation; it is not a proof of error.",
        "- A source continuation or lexical adjacency is a research lead, not a proven dependency.",
        "- A marked complete comparator does not change the strict corpus score or imply author intention.",
        "- Source offsets are reported only if the corpus mapper explicitly marked them exact.",
        "- No rule, budget, recognizer, ranking or original text is changed.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("register", "register_summary", "preflight", "lexical", "dialogue",
                 "dialogue_summary", "comparators", "out_dir"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    rows, summary = synthesize(
        read_jsonl(args.register),
        json.loads(args.register_summary.read_text(encoding="utf8")),
        read_jsonl(args.preflight), read_jsonl(args.lexical),
        read_jsonl(args.dialogue),
        json.loads(args.dialogue_summary.read_text(encoding="utf8")),
        read_jsonl(args.comparators),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "residual_evidence_synthesis.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf8")
    (args.out_dir / "residual_evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf8")
    (args.out_dir / "residual_evidence_report.md").write_text(render(rows, summary), encoding="utf8")
    print("RESIDUAL_EVIDENCE_SUMMARY", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
