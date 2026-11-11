"""Reproducible, bounded, one-pass diagnosis of cleaned novel sentences.

The forest state budget and k-best WORK budget are independent. Neither a
timed-out parse nor a saturated search proves lack of grammatical coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
import re
from pathlib import Path
import signal
from time import perf_counter

from scripts.corpus_samples import BANDS, choose_cases, sample_spread
from seman_parser.engine import Parser, ParserResources
from research.verbnet_lr.corpus_pipeline import parse_corpus_case, prepare_corpus_input
from seman_parser.structural_units import source_unit_signals

ROOT = Path(__file__).resolve().parents[1]
# The *current* 500-case cohort is explicitly pinned after sampling with the
# single active segmenter. Its predecessor is available in Git history only.
CURRENT_COHORT_MANIFEST = Path(__file__).resolve().parents[2] / "docs" / "CURRENT_COHORT.json"
EXPECTED_500_COHORT_SHA256 = json.loads(
    CURRENT_COHORT_MANIFEST.read_text(encoding="utf-8")
)["cohort_sha256"]
STATUSES = (
    "complete", "both_budgets_exceeded", "forest_budget_exceeded",
    "kbest_budget_exceeded", "no_structural_root",
    "roots_without_valid_analysis", "timeout", "error",
)
MEANINGS = {
    "complete": "Full-span parse found under current grammar; tree quality is not independently certified",
    "both_budgets_exceeded": "Recognition and k-best both saturated",
    "forest_budget_exceeded": "Recognition stopped at forest item ceiling",
    "kbest_budget_exceeded": "Extraction stopped at k-best work ceiling",
    "no_structural_root": "No full-span clause found without saturation",
    "roots_without_valid_analysis": "Roots exist, but none unifies to a valid analysis",
    "timeout": "Deadline reached (no coverage conclusion)",
    "error": "Execution error (no coverage conclusion)",
}


class SentenceDeadline(Exception):
    pass


def _deadline(_signum, _frame):
    raise SentenceDeadline()


def select_cases(count: int):
    """Exactly count sentences, deterministically spread over 4 books x 4 bands."""
    if count < 1:
        raise ValueError("count must be positive")
    per_book_band = math.ceil(count / (4 * len(BANDS)))
    pool, sources = choose_cases(per_book_band)
    if len(pool) < count:
        raise ValueError(f"Only {len(pool)} eligible sentences for {count} requested")
    return sample_spread(pool, count), sources


def classify(completed: bool, stats: dict) -> str:
    """Exclusive headline; independent budget flags remain in the JSONL."""
    if completed:
        return "complete"
    # Public Parser.parse can try a scoped quote grammar before falling back
    # to the ordinary grammar. A failed, resource-limited attempt still makes
    # the overall failure inconclusive, even if the fallback has no root.
    dialogue = stats.get("dialogue_attempt") or {}
    forest = bool(stats.get("budget_exceeded") or dialogue.get("budget_exceeded"))
    kbest = bool(
        stats.get("kbest_budget_exceeded")
        or dialogue.get("kbest_budget_exceeded")
    )
    if forest and kbest:
        return "both_budgets_exceeded"
    if forest:
        return "forest_budget_exceeded"
    if kbest:
        return "kbest_budget_exceeded"
    if (
        int(stats.get("structural_root_nodes", 0)) == 0
        and int(dialogue.get("structural_root_nodes", 0)) == 0
    ):
        return "no_structural_root"
    return "roots_without_valid_analysis"



def _json_lexical(value):
    if isinstance(value, dict):
        return {str(k): _json_lexical(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_lexical(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _full_subtoken_path(
    start: int, end: int, candidates, source_text: str,
) -> bool:
    """Check that a sequence of actually licensed lexical edges covers a token.

    Distinguish valid morphology from accidental WordNet subword readings.
    In particular, N/ADJ + n't does NOT constitute an English auxiliary
    negative, even though the substring spans the whole written token.
    """
    allowed = [
        edge for edge in candidates
        if start <= edge.span_start < edge.span_end <= end
        and (edge.span_start, edge.span_end) != (start, end)
        and edge.surface.casefold()
        == source_text[edge.span_start:edge.span_end].casefold()
    ]
    # Track the immediate predecessor's category, not just reachable spans.
    categories_at = {start: {None}}
    auxiliary_stems = {"AUX", "AUX-BE", "COPULA", "HAVE", "MODAL"}
    for edge in sorted(allowed, key=lambda row: (row.span_start, row.span_end)):
        preceding = categories_at.get(edge.span_start, set())
        if edge.source == "contraction-clitic" and edge.category == "NEG":
            preceding = preceding.intersection(auxiliary_stems)
        if preceding:
            categories_at.setdefault(edge.span_end, set()).add(edge.category)
    return end in categories_at


def lexical_diagnostics(lattice) -> dict:
    """Return all parser-visible POS and sense alternatives, never just best."""
    candidates = lattice.candidates

    def detail(candidate):
        return {
            "span": [candidate.span_start, candidate.span_end],
            "surface": candidate.surface,
            "category": candidate.category,
            "lemma": candidate.lemma,
            "normalized": candidate.normalized,
            "source": candidate.source,
            "score": candidate.score,
            "features": _json_lexical(candidate.features.as_dict()),
            "syntactic_constraints": _json_lexical(candidate.syntactic_constraints),
            "provenance": _json_lexical(dict(candidate.provenance)),
            "sense_ids": list(candidate.sense_ids),
            "interpretations": [{
                "sense_id": option.sense_id,
                "lemma": option.lemma,
                "score": option.score,
                "provenance": _json_lexical(dict(option.provenance)),
            } for option in candidate.interpretations],
        }

    rows = []
    for token in lattice.tokens:
        exact = [c for c in candidates
                 if (c.span_start, c.span_end) == (token.start, token.end)]
        covering = [c for c in candidates
                    if c.span_start <= token.start and c.span_end >= token.end
                    and (c.span_start, c.span_end) != (token.start, token.end)]
        subtoken = [c for c in candidates
                    if token.start <= c.span_start < c.span_end <= token.end
                    and (c.span_start, c.span_end) != (token.start, token.end)]
        split_coverage = _full_subtoken_path(
            token.start, token.end, subtoken, lattice.text
        )
        word = any(ch.isalpha() for ch in token.text)
        rows.append({
            "index": token.index, "surface": token.text,
            "span": [token.start, token.end], "is_word": word,
            "categories": sorted({c.category for c in exact}),
            "candidate_count": len(exact), "multiword_cover_count": len(covering),
            "split_candidate_count": len(subtoken),
            "has_split_candidate_path": split_coverage,
            "no_exact_candidate": word and not exact,
            "no_candidate_or_cover": word and not exact and not covering
                                     and not split_coverage,
            "candidates": [detail(c) for c in exact],
            "covering_multiword_candidates": [detail(c) for c in covering],
            "subtoken_candidates": [detail(c) for c in subtoken],
        })
    return {
        "schema": "seman2-failed-sentence-lexicon-v2",
        "scope": "parser-visible lexical candidates after lattice filters",
        "tokens": rows,
        "word_count": sum(row["is_word"] for row in rows),
        "words_without_exact_candidate": [
            row["surface"] for row in rows if row["no_exact_candidate"]
        ],
        "words_without_any_candidate": [
            row["surface"] for row in rows if row["no_candidate_or_cover"]
        ],
        "lexical_candidate_count": len(candidates),
    }


def recurring_issues(rows: list[dict], *, minimum_cases: int = 3) -> dict:
    """Descriptive frequencies in failed cases, without claiming causality.

    Count DISTINCT sentences supporting a lexical gap or category n-gram,
    so repeated tokens in one sentence cannot dominate the report.
    """
    failures = [row for row in rows if row["status"] != "complete"]
    categories = (
        "word_without_candidate",
        "word_without_exact_candidate",
        "category_bigram",
        "category_trigram",
    )
    counts = {name: Counter() for name in categories}
    examples = {name: {} for name in categories}
    for row in failures:
        lex = row.get("lexical_diagnostic")
        if not lex:
            continue
        tokens = [t for t in lex["tokens"] if t["is_word"]]
        patterns = {
            "word_without_candidate": {
                token["surface"].casefold() for token in tokens
                if token["no_candidate_or_cover"]
            },
            "word_without_exact_candidate": {
                token["surface"].casefold() for token in tokens
                if token["no_exact_candidate"]
            },
        }
        sequence = tuple(
            "/".join(token["categories"]) or "NO_EXACT_LEXICAL_CANDIDATE"
            for token in tokens
        )
        for n, name in ((2, "category_bigram"), (3, "category_trigram")):
            patterns[name] = {
                " + ".join(sequence[i:i + n])
                for i in range(len(sequence) - n + 1)
            }
        for name, keys in patterns.items():
            for pattern in keys:
                counts[name][pattern] += 1
                identifiers = examples[name].setdefault(pattern, [])
                if len(identifiers) < 3:
                    identifiers.append(row["case_id"])
    def report(name):
        return [
            {"pattern": key, "failed_sentence_count": count,
             "example_case_ids": examples[name][key]}
            for key, count in sorted(
                counts[name].items(), key=lambda item: (-item[1], item[0])
            )
            if count >= minimum_cases
        ]
    return {
        "schema": "seman2-novel-recurring-failure-signals-v1",
        "denominator": {
            "sampled": len(rows), "failed": len(failures),
            "with_lexical_evidence": sum(
                row.get("lexical_diagnostic") is not None for row in failures
            ),
        },
        "minimum_distinct_failed_sentences": minimum_cases,
        **{name: report(name) for name in categories},
        "notes": [
            "Counts distinct failed sentences, not token occurrences.",
            "Correlations are not established causes of grammar failure.",
            "Post-filter lattice candidates are not the full raw WordNet inventory.",
            "Word frequencies are not controlled for successful cases.",
        ],
    }


def word_category_sequence(lattice) -> list[str]:
    """Compact lexical signatures for BOTH successful and failed cases."""
    categories = {}
    for c in lattice.candidates:
        categories.setdefault((c.span_start, c.span_end), set()).add(c.category)
    result = []
    for token in lattice.tokens:
        if not any(ch.isalpha() for ch in token.text):
            continue
        direct = "/".join(sorted(
            categories.get((token.start, token.end), ())
        ))
        if direct:
            result.append(direct)
        elif _full_subtoken_path(
            token.start, token.end, lattice.candidates, lattice.text
        ):
            result.append("SPLIT_LEXICAL_CANDIDATES")
        else:
            result.append("NO_EXACT_LEXICAL_CANDIDATE")
    return result


def contrast_category_patterns(rows: list[dict], *, min_support: int = 5) -> dict:
    """Compare patterns in grammatical failures AND successful parses.

    Saturations/timeouts cannot be treated as grammatical counterexamples.
    These are exploratory enrichment ratios with smoothing, not causality.
    """
    usable = [
        row for row in rows
        if row.get("lexical_category_sequence") is not None
        and row["status"] in (
            "complete", "no_structural_root", "roots_without_valid_analysis"
        )
    ]
    failures = [r for r in usable if r["status"] != "complete"]
    successes = [r for r in usable if r["status"] == "complete"]
    failure_n, success_n = len(failures), len(successes)
    by_pattern = {}
    for row in usable:
        sequence = row["lexical_category_sequence"]
        is_failure = row["status"] != "complete"
        for width in (2, 3):
            patterns = set(
                " + ".join(sequence[i:i + width])
                for i in range(len(sequence) - width + 1)
            )
            for pattern in patterns:
                key = (width, pattern)
                counts = by_pattern.setdefault(key, [0, 0, []])
                counts[0 if is_failure else 1] += 1
                if is_failure and len(counts[2]) < 3:
                    counts[2].append(row["case_id"])
    result = []
    for (width, pattern), (fail, success, examples) in by_pattern.items():
        if fail + success < min_support or fail < 3:
            continue
        # Smoothed shares prevent division by zero and reduce small-N noise.
        fshare = (fail + 0.5) / (failure_n + 1)
        sshare = (success + 0.5) / (success_n + 1)
        result.append({
            "gram_length": width, "pattern": pattern,
            "failed_sentence_count": fail,
            "successful_sentence_count": success,
            "failure_share": round(fail / failure_n, 4) if failure_n else 0,
            "success_share": round(success / success_n, 4) if success_n else 0,
            "enrichment_ratio": round(fshare / sshare, 3),
            "example_case_ids": examples,
        })
    result.sort(key=lambda x: (
        -x["enrichment_ratio"], -x["failed_sentence_count"], x["pattern"]
    ))
    return {
        "schema": "seman2-novel-contrastive-patterns-v2",
        "counts": {
            "usable": len(usable), "grammatical_failures": failure_n,
            "completed": success_n,
            "excluded_inconclusive": len(rows) - len(usable),
        },
        "min_combined_support": min_support,
        "min_failed_support": 3,
        "patterns": result,
        "notes": [
            "Sentence-level presence rather than token occurrence counts.",
            "Uses ALL parser-visible POS candidates for every word.",
            "Excludes timeout, error, and budget-saturated incompletes.",
            "Patterns are not known grammatical-error causes.",
            "Completion certifies a parse tree, not its semantic/gold correctness.",
        ],
    }



def canonical_residual_audit(rows: list[dict]) -> tuple[dict, list[dict]]:
    """Investigate genuine failures of the public parser on balanced input.

    Surface tags are descriptive signals, never proof of the failure's cause.
    There is no second parse route or hidden historical fallback.
    """
    statuses = Counter()
    families = Counter()
    residuals = []
    for row in rows:
        status = row["status"]
        if status not in STATUSES:
            raise ValueError(f"Unknown canonical diagnostic status: {status}")
        statuses[status] += 1
        if status == "complete":
            continue
        sentence = row["sentence"]
        words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*", sentence.casefold())
        word_set = set(words)
        tags = []
        if word_set & {"and", "but", "nor", "or"}:
            tags.append("coordination_surface")
        if word_set & {"which", "who", "whom", "whose", "that", "what"}:
            tags.append("relative_or_wh_surface")
        if "to" in word_set:
            tags.append("to_surface")
        if any(w.endswith("ing") for w in words):
            tags.append("ing_surface")
        if sentence.lstrip()[:1].islower():
            tags.append("lowercase_initial_surface")
        if row.get("canonical_analysis_text") != sentence:
            tags.append("quote_transfer_changed_input")
        lexical = row.get("lexical_diagnostic") or {}
        missing = lexical.get("words_without_any_candidate", [])
        if missing:
            tags.append("lexical_gap")
        if not tags:
            tags.append("other_surface")
        families.update(tags)
        residuals.append({
            "case_id": row["case_id"],
            "index": row["index"],
            "book_id": row["book_id"],
            "band": row["band"],
            "sentence": sentence,
            "source_text": row["source_text"],
            "canonical_analysis_text": row.get("canonical_analysis_text", sentence),
            "canonical_status": status,
            "quote_transfer_changed_input": (
                row.get("canonical_analysis_text", sentence) != sentence
            ),
            "surface_tags": tags,
            "words_without_any_candidate": missing,
        })
    n = len(rows)
    completed = statuses["complete"]
    return ({
        "schema": "seman2-canonical-residual-audit-v2",
        "n": n, "completed": completed,
        "coverage_percent": round(100 * completed / n, 2) if n else 0.0,
        "statuses": {status: statuses[status] for status in STATUSES},
        "surface_tags_nonexclusive": dict(sorted(families.items())),
        "remaining": len(residuals),
        "caution": (
            "The SAME public Parser.parse is used for all canonical cases. "
            "Tags are correlations, not proven grammar-error causes."
        ),
    }, residuals)



# These signatures describe observable constructions, NOT proven diagnoses.
# Evaluate them on all 500 cases, including successful negative controls.
_CONSTRUCTION_PATTERNS = {
    "relative_preposition_pied_piping": re.compile(
        r",\s*(?:and\s+)?(?:to|of|with|in|for|by|on|at|from)\s+"
        r"(?:which|whom|whose)\b", re.I,
    ),
    "parenthetical_between_commas": re.compile(
        r",\s*(?:indeed|however|therefore|you\s+know|i\s+think|"
        r"i\s+believe|of\s+course|perhaps|certainly|nevertheless)\s*,",
        re.I,
    ),
    "copular_adjective_finite_complement": re.compile(
        r"\b(?:am|is|are|was|were|be|been)\s+"
        r"(?:very\s+|quite\s+|really\s+|so\s+)*"
        r"(?:afraid|sure|certain|glad)\s+(?:that\s+)?"
        r"(?:I|you|he|she|we|they|it)\b|"
        r"\b(?:are|is|was|were)\s+(?:you|he|she|we|they|it)\s+"
        r"(?:very\s+|quite\s+|really\s+|so\s+)*"
        r"(?:afraid|sure|certain|glad)\s+(?:that\s+)?"
        r"(?:I|you|he|she|we|they|it)\b",
        re.I,
    ),
    "comma_followed_by_participial_phrase": re.compile(
        r",\s*(?:\w+\s+){0,2}\w+ing\b", re.I,
    ),
    "comma_followed_by_coordinator": re.compile(
        r",\s*(?:and|but|or)\b", re.I,
    ),
}
# Corpus-wide, non-exclusive grammatical/orthographic features. Each is
# compared with *successful* cases in the same fixed cohort; no phrase index,
# individual literary title or "rescue" rule is part of the classifier.
_CONSTRUCTION_PATTERNS.update({
    "finite_subordination_surface": re.compile(
        r"\b(?:that|when|while|before|after|if|though|although|unless|because|since)\b", re.I),
    "relative_or_free_wh_surface": re.compile(
        r"\b(?:which|who|whom|whose|what|where|wherever)\b", re.I),
    "nonfinite_to_verb_surface": re.compile(r"\bto\s+[A-Za-z][A-Za-z'-]*\b", re.I),
    "repeated_coordination": re.compile(
        r"\b(?:and|but|or|nor)\b.{5,}\b(?:and|but|or|nor)\b", re.I),
    "initial_coordinator_or_subordinator": re.compile(
        r"^\s*['\"“‘]?\s*(?:and|but|nor|or|which|that|as|while|if|though)\b", re.I),
    "paired_comma_interruption": re.compile(r",[^,]{2,85},", re.I),
    "parenthesized_or_dashed_interruption": re.compile(
        r"\([^)]{3,}\)|--[^-]{3,}--|—[^—]{3,}—"),
    "negative_auxiliary_or_copula": re.compile(
        r"\b(?:do|does|did|has|have|had|can|could|will|would|shall|should|is|are|was|were)"
        r"\s+not\b|\b(?:don't|doesn't|didn't|can't|couldn't|won't|wouldn't|isn't|wasn't)\b", re.I),
    "comparative_parallelism": re.compile(
        r"\b(?:more|less|rather|so|such|as|than)\b", re.I),
    "passive_or_perfect_complex": re.compile(
        r"\b(?:was|were|been|being|had|have|has)\s+(?:\w+\s+){0,2}\w+(?:ed|en)\b", re.I),
    "quotation_or_reporting": re.compile(r"['\"“”‘’]", re.I),
    "multiple_clausal_commas": re.compile(r"(?:,[^,]*){3,}"),
    "gerund_or_participial_adjunct": re.compile(r"\b[A-Za-z]+ing\b", re.I),
})

_INCONCLUSIVE_STATUSES = frozenset({
    "timeout", "error", "forest_budget_exceeded",
    "kbest_budget_exceeded", "both_budgets_exceeded",
})


def _length_band_failure_baselines(rows: list[dict]) -> dict[str, float]:
    """One rate per token-length band, excluding uncensored resource limits."""
    counts: dict[str, list[int]] = {}
    for row in rows:
        if row["status"] not in (
            "complete", "no_structural_root", "roots_without_valid_analysis"
        ):
            continue
        band = str(row.get("band", "unbanded"))
        count = counts.setdefault(band, [0, 0])
        count[0] += 1
        count[1] += int(row["status"] != "complete")
    return {
        band: failed / decided
        for band, (decided, failed) in counts.items() if decided
    }


def _length_adjusted_outcome(
    decided_rows: list[dict], failure_count: int,
    band_rates: dict[str, float],
) -> dict:
    """Expected failures for this subset at cohort background rates by band."""
    expected = sum(
        band_rates.get(str(row.get("band", "unbanded")), 0.0)
        for row in decided_rows
    )
    return {
        "length_adjusted_expected_failures": round(expected, 2),
        "length_adjusted_excess_failures": round(failure_count - expected, 2),
        "length_adjusted_relative_risk": (
            round(failure_count / expected, 2) if expected > 0 else None
        ),
    }


def construction_cluster_audit(rows: list[dict]) -> dict:
    """Case-level, nonexclusive failure enrichment against the SAME successes.

    No second parser call, grammar guess, or edited quotation is allowed.
    An incomplete case due to budget/deadline is explicitly inconclusive.
    """
    groups = []
    band_rates = _length_band_failure_baselines(rows)
    for name, pattern in _CONSTRUCTION_PATTERNS.items():
        matched = [
            row for row in rows
            if pattern.search(row.get("canonical_analysis_text", row["sentence"]))
        ]
        successes = [r for r in matched if r["status"] == "complete"]
        inconclusive = [
            r for r in matched if r["status"] in _INCONCLUSIVE_STATUSES
        ]
        failures = [
            r for r in matched
            if r["status"] != "complete"
            and r["status"] not in _INCONCLUSIVE_STATUSES
        ]
        decided = len(successes) + len(failures)
        groups.append({
            "construction": name,
            "matched": len(matched),
            "successful": len(successes),
            "conclusive_failures": len(failures),
            "inconclusive": len(inconclusive),
            "conclusive_failure_percent": (
                round(100 * len(failures) / decided, 2) if decided else None
            ),
            **_length_adjusted_outcome(successes + failures, len(failures), band_rates),
            "failing_case_indices": [r["index"] for r in failures],
            "inconclusive_case_indices": [r["index"] for r in inconclusive],
            "successful_control_indices": [r["index"] for r in successes[:8]],
            "failure_examples": [
                {"index": r["index"], "book_id": r["book_id"],
                 "analysis_text": r.get("canonical_analysis_text", r["sentence"]),
                 "status": r["status"]}
                for r in failures[:8]
            ],
        })
    groups.sort(key=lambda r: (
        -r["length_adjusted_excess_failures"],
        -r["conclusive_failures"], r["construction"],
    ))
    return {
        "schema": "seman2-construction-clusters-v2",
        "cohort_size": len(rows),
        "total_conclusive_failures": sum(
            r["status"] not in _INCONCLUSIVE_STATUSES
            and r["status"] != "complete" for r in rows
        ),
        "total_inconclusive": sum(
            r["status"] in _INCONCLUSIVE_STATUSES for r in rows
        ),
        "groups": groups,
        "interactions": construction_interaction_audit(rows),
        "cautions": [
            "These are surface signatures, not proof of a missing rule.",
            "Groups overlap; their failures MUST NOT be summed.",
            "Token-length strata control for part of the long-sentence confound; "
            "they do not establish a causal missing construction.",
            "Each rate uses matching successes as controls and excludes "
            "budget failures and timeouts.",
            "The corpus is unchanged and every case uses public Parser.parse.",
        ],
    }



def construction_interaction_audit(rows: list[dict], *, min_support: int = 5) -> dict:
    """Find co-occurring observable constructions enriched in true failures.

    Compare each pair with successful control sentences in the same cohort.
    These are overlapping observational associations, not grammar rules,
    not root-cause diagnoses, and not a way to relabel budget-limited cases.
    """
    conclusive = [
        row for row in rows
        if row["status"] == "complete" or row["status"] in (
            "no_structural_root", "roots_without_valid_analysis"
        )
    ]
    failed = sum(row["status"] != "complete" for row in conclusive)
    baseline = failed / len(conclusive) if conclusive else 0.0
    band_rates = _length_band_failure_baselines(conclusive)
    per_case = [
        (
            row,
            {name for name, pattern in _CONSTRUCTION_PATTERNS.items()
             if pattern.search(row.get("canonical_analysis_text", row["sentence"]))}
        )
        for row in conclusive
    ]
    patterns = sorted(_CONSTRUCTION_PATTERNS)
    pairs = []
    for i, first in enumerate(patterns):
        for second in patterns[i + 1:]:
            subset = [row for row, signatures in per_case
                      if first in signatures and second in signatures]
            if len(subset) < min_support:
                continue
            failures = [row for row in subset if row["status"] != "complete"]
            controls = [row for row in subset if row["status"] == "complete"]
            observed = len(failures) / len(subset)
            pairs.append({
                "signatures": [first, second],
                "support": len(subset),
                "conclusive_failures": len(failures),
                "successful_controls": len(controls),
                "failure_percent": round(observed * 100, 2),
                "baseline_failure_percent": round(baseline * 100, 2),
                "relative_risk": round(observed / baseline, 2) if baseline else None,
                "excess_failures_vs_baseline": round(
                    len(failures) - len(subset) * baseline, 2
                ),
                **_length_adjusted_outcome(subset, len(failures), band_rates),
                "failure_indices": [row["index"] for row in failures],
                "control_indices": [row["index"] for row in controls[:5]],
            })
    # Rank by absolute surplus of failures, not by inflated percentages from
    # one or two rare examples; evidence still requires both sample sizes.
    pairs.sort(key=lambda p: (
        -p["length_adjusted_excess_failures"], -p["conclusive_failures"],
        -p["support"], p["signatures"]
    ))
    return {
        "conclusive_total": len(conclusive),
        "conclusive_failures": failed,
        "excluded_resource_limited": len(rows) - len(conclusive),
        "baseline_failure_percent": round(baseline * 100, 2),
        "failure_percent_by_length_band": {
            band: round(rate * 100, 2) for band, rate in sorted(band_rates.items())
        },
        "pairs": pairs,
        "interpretation": "observational enrichment versus successful same-cohort controls",
    }


def compact_stats(stats: dict) -> dict:
    names = (
        "engine", "structural_root_nodes", "forest_nodes", "partial_states",
        "structural_derivations", "partial_derivations", "partial_proposals",
        "recognition_operations", "recognition_ms", "best_ms",
        "combinations_visited_for_best", "combinations_visited_total",
        "kbest_work_units", "unification_attempts", "unification_rejections",
        "hint_unification_attempts", "hint_unification_rejections",
    )
    return {key: stats.get(key, 0) for key in names}


def tally(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "completed": sum(r["status"] == "complete" for r in rows),
        "statuses": {s: sum(r["status"] == s for r in rows) for s in STATUSES},
        "forest_budget_flag": sum(bool(r.get("forest_budget_exceeded")) for r in rows),
        "kbest_budget_flag": sum(bool(r.get("kbest_budget_exceeded")) for r in rows),
        "structural_roots_present": sum(r.get("structural_root_nodes", 0) > 0 for r in rows),
        "complete_with_forest_saturation": sum(
            r["status"] == "complete" and bool(r.get("forest_budget_exceeded"))
            for r in rows
        ),
    }


def render_markdown(summary: dict, rows: list[dict]) -> str:
    total = summary["totals"]
    limits = summary["limits"]
    output = [
        "# Seman2 — diagnostic des phrases de romans",
        "",
        f"Analyses certifiées : {total['completed']}/{total['n']} "
        f"({summary['coverage_percent']:.1f} %).",
        "",
        f"Reconnaissance : {limits['max_items']} états ; k-best : "
        f"{limits['kbest_work_limit']} unités de travail ; délai : "
        f"{limits['deadline_seconds']} s / phrase.",
        "",
        "ATTENTION : les unités k-best ne sont pas les combinaisons visitées. "
        "Les deux mesures figurent dans per_sentence.jsonl.",
        "",
        "## Cause principale (catégories exclusives)",
        "",
        "| Cause | Phrases | Interprétation |",
        "|---|---:|---|",
    ]
    for status in STATUSES:
        output.append(
            f"| {status} | {total['statuses'][status]} | {MEANINGS[status]} |"
        )
    output.extend([
        "",
        "## Drapeaux indépendants, même sur des analyses complètes",
        "",
        f"- Forêt saturée : {total['forest_budget_flag']}",
        f"- K-best saturé : {total['kbest_budget_flag']}",
        f"- Racines structurelles présentes : {total['structural_roots_present']}",
        f"- Complètes mais forêt saturée : {total['complete_with_forest_saturation']}",
        "",
        "## Par longueur de phrase",
        "",
        "| Tokens | n | Complètes | Forêt saturée | K-best saturé |",
        "|---|---:|---:|---:|---:|",
    ])
    for band, row in summary["by_band"].items():
        output.append(
            f"| {band} | {row['n']} | {row['completed']} | "
            f"{row['forest_budget_flag']} | {row['kbest_budget_flag']} |"
        )
    output.extend([
        "",
        "## Premières phrases non complètes (maximum 15)",
        "",
        "| Index | Livre | Tokens | Cause | Racines | Unités k-best | Temps (ms) |",
        "|---:|---:|---:|---|---:|---:|---:|",
    ])
    for row in [r for r in rows if r["status"] != "complete"][:15]:
        output.append(
            f"| {row['index'] + 1} | {row['book_id']} | {row['tokens']} | "
            f"{row['status']} | {row.get('structural_root_nodes', '-')} | "
            f"{row.get('kbest_work_units', '-')} | {row['wall_ms']} |"
        )
    output.extend([
        "",
        "Le fichier per_sentence.jsonl conserve aussi toutes les phrases, "
        "les compteurs de combinaisons et d'unification et les erreurs.",
        "Une saturation, un délai ou une racine structurelle invalide ne "
        "doivent pas être confondus avec une absence certaine de grammaire.",
        "",
    ])
    canonical = summary.get("canonical_audit")
    if canonical is not None:
        output.extend([
            "",
            "## Couverture canonique après transfert réel des guillemets",
            "",
            f"Analyses certifiées : {canonical['completed']}/{canonical['n']} "
            f"({canonical['coverage_percent']:.1f} %).",
            f"Cas toujours non complets : {canonical['remaining']}.",
            "",
            "Les signatures de surface sont non exclusives et ne prouvent "
            "aucune cause grammaticale. Voir canonical_residuals.jsonl.",
            "",
            "| Signature descriptive | Cas canoniques non complets |",
            "|---|---:|",
        ])
        for tag, count in sorted(
            canonical["surface_tags_nonexclusive"].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            output.append(f"| {tag} | {count} |")
    clusters = summary.get("construction_clusters")
    if clusters:
        output.extend([
            "",
            "## Constructions grammaticales récurrentes : échecs et témoins",
            "",
            "Signatures de surface, **pas** diagnostic automatique de la cause. "
            "Cohortes chevauchantes ; les cas saturés et les délais sont exclus "
            "du taux conclusif. Les réussites comptent comme témoins.",
            "",
            "| Construction candidate | Cas | Échecs conclusifs | Réussites | "
            "Inconclusifs | Taux d'échec conclusif |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for group in clusters["groups"]:
            rate = group["conclusive_failure_percent"]
            formatted = "n/a" if rate is None else f"{rate:.1f} %"
            output.append(
                f"| {group['construction']} | {group['matched']} | "
                f"{group['conclusive_failures']} | {group['successful']} | "
                f"{group['inconclusive']} | {formatted} |"
            )
            if group["conclusive_failures"]:
                output.append(
                    f"  - Indices des échecs : "
                    + ", ".join(str(i) for i in group["failing_case_indices"])
                )
        output.append("")
    patterns = summary["recurrent_issues"]
    output.extend([
        "",
        "## Motifs récurrents parmi les échecs",
        "",
        f"Seuil : {patterns['minimum_distinct_failed_sentences']} phrases "
        "échouées distinctes. Cooccurrences seulement, sans causalité prouvée. "
        "Un motif courant aussi dans les réussites peut être non discriminant.",
        "",
    ])
    for key, title in (
        ("word_without_candidate", "Mots sans candidat lexical"),
        ("word_without_exact_candidate", "Mots sans candidat exact"),
        ("category_bigram", "Bigrams de catégories candidates"),
        ("category_trigram", "Trigrams de catégories candidates"),
    ):
        output.extend([
            f"### {title}", "",
            "| Motif | Phrases échouées | Exemples |",
            "|---|---:|---|",
        ])
        for item in patterns[key][:25]:
            name = item["pattern"].replace("|", "\\|")
            ids = ", ".join(item["example_case_ids"])
            output.append(
                f"| {name} | {item['failed_sentence_count']} | {ids} |"
            )
        if not patterns[key]:
            output.append("| Aucun motif répétitif au seuil choisi | 0 | — |")
        output.append("")
    output.extend([
        "",
        "## Corpus de cas échoués — détail lexical intégral",
        "",
        "Toutes les catégories candidates (post-filtrage du treillis), sous-types "
        "et comptes de sens. Les identifiants de sens, provenances, contraintes "
        "et analyses multi-mots sont conservés dans failed_sentences.jsonl.",
        "",
    ])
    contrasts = summary["pattern_contrasts"]
    output.extend([
        "",
        "## Signatures de catégories surreprésentées parmi les échecs",
        "",
        "Comparaison sur les mêmes 500 cas ; seuls les statuts grammaticaux "
        "conclusifs sont inclus (pas les délais/budgets). Les ratios sont "
        "lissés et exploratoires, sans preuve de cause.",
        "",
        "| Motif | Échecs | Réussites | Rapport enrichissement |",
        "|---|---:|---:|---:|",
    ])
    for match in contrasts["patterns"][:30]:
        pattern = match["pattern"].replace("|", "\\|")
        output.append(
            f"| {pattern} | {match['failed_sentence_count']} | "
            f"{match['successful_sentence_count']} | "
            f"{match['enrichment_ratio']} |"
        )
    output.append("")
    for row in rows:
        if row["status"] == "complete":
            continue
        output.extend([
            f"### Cas {row['case_id']} — {row['status']}",
            "",
            f"Roman {row['book_id']}, index {row['index'] + 1}",
            "",
            f"> {row['sentence']}",
            "",
        ])
        if row.get("source_text") != row["sentence"]:
            output.extend([
                "Extrait original avant normalisation :",
                "",
                f"> {row.get('source_text', '')}",
                "",
            ])
        lex = row.get("lexical_diagnostic")
        if lex is None:
            output.extend(["Treillis indisponible avant interruption.", ""])
            continue
        output.extend([
            "| Mot | Catégories et traits syntaxiques | Sens |",
            "|---|---|---:|",
        ])
        for token in lex["tokens"]:
            labels = []
            sense_count = 0
            for candidate in token["candidates"]:
                features = candidate["features"]
                relevant = ("subcat", "vform", "number", "person",
                            "voice", "tense", "wh", "negation")
                desc = ",".join(
                    f"{key}={features[key]}" for key in relevant if key in features
                )
                labels.append(candidate["category"] + (f" ({desc})" if desc else ""))
                sense_count += len(candidate["sense_ids"])
            if not labels:
                labels = ["(aucun candidat exact)"]
            if token["multiword_cover_count"]:
                labels.append(
                    f"+{token['multiword_cover_count']} couverture(s) multi-mots"
                )
            label = "; ".join(dict.fromkeys(labels)).replace("|", "\\|")
            surface = token["surface"].replace("|", "\\|")
            output.append(f"| {surface} | {label} | {sense_count} |")
        output.extend([
            "",
            f"Mots sans aucun candidat : {lex['words_without_any_candidate']}",
            "",
        ])
    return "\n".join(output)


def run(
    args: argparse.Namespace, *,
    selected_override: list[dict] | None = None,
    source_description: str | None = None,
) -> dict:
    if args.max_items < 1 or args.kbest_work_limit < 1 or args.deadline_seconds <= 0:
        raise ValueError("Budgets and deadline must be positive")
    if selected_override is None:
        selected, sources = select_cases(args.count)
    else:
        selected, sources = selected_override, []
    if len(selected) != args.count:
        raise AssertionError("The cohort must contain exactly the requested count")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "cohort.jsonl").open(
        "w", encoding="utf8"
    ) as cohort_stream:
        for index, case in enumerate(selected):
            cohort_stream.write(json.dumps({
                "index": index, "book_id": case["book_id"],
                "ordinal": case["ordinal"], "band": case["band"],
                "tokens": case["tokens"], "sentence": case["text"],
                "source_text": case.get("source_text", case["text"]),
                "semicolon_split": bool(case.get("semicolon_split")),
                "synthetic_prefix": case.get("synthetic_prefix", ""),
                "synthetic_suffix": case.get("synthetic_suffix", ""),
                "synthetic_terminal": bool(case.get("synthetic_terminal")),
            }, ensure_ascii=False) + "\n")
    cohort_digest = sha256(
        (args.out_dir / "cohort.jsonl").read_bytes()
    ).hexdigest()
    if (selected_override is None and args.count == 500
            and cohort_digest != EXPECTED_500_COHORT_SHA256):
        raise ValueError(
            "The current 500-case reference cohort changed: "
            f"expected {EXPECTED_500_COHORT_SHA256}, got {cohort_digest}. "
            "Review corpus extraction/sampling changes before updating the pin."
        )
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=args.max_items)
    # Warm lexical lookup before any per-sentence deadline.
    parser.parse("John opened the box.")  # One public warm-up route
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    old_handler = signal.signal(signal.SIGALRM, _deadline)
    started = perf_counter()
    try:
        with (args.out_dir / "per_sentence.jsonl").open(
            "w", encoding="utf8", buffering=1
        ) as stream:
            for index, case in enumerate(selected):
                source_text = case.get("source_text", case["text"])
                row = {
                    "index": index, "book_id": case["book_id"],
                    "ordinal": case["ordinal"], "band": case["band"],
                    "tokens": case["tokens"], "sentence": case["text"],
                    "source_text": source_text,
                    "structural_surface_signals": source_unit_signals(source_text),
                    "structural_functions": [
                        p["function"] for p in case.get("structural_constituents", ())
                    ],
                    "structural_relations": [
                        p["relation"] for p in case.get("structural_constituents", ())
                    ],
                    "quotation_status": case.get("quotation_status", "not_supplied"),
                    "discourse_function": case.get("discourse_function", "not_supplied"),
                    "discourse_relation": case.get("discourse_relation", "not_supplied"),
                    "discourse_evidence": case.get("discourse_evidence", "not_supplied"),
                    "semicolon_split": bool(case.get("semicolon_split")),
                    "synthetic_prefix": case.get("synthetic_prefix", ""),
                    "synthetic_suffix": case.get("synthetic_suffix", ""),
                    "synthetic_terminal": bool(case.get("synthetic_terminal")),
                    "case_id": str(case["book_id"]) + ":" + sha256(
                        source_text.encode("utf8")
                    ).hexdigest()[:16],
                    "sha256": sha256(case["text"].encode("utf8")).hexdigest(),
                }
                # The official measurement is the quote-balanced input
                # analyzed through exactly the public Parser.parse route.
                balanced = prepare_corpus_input(case)
                row["analysis_contract"] = "corpus_pipeline:public-parser-v2"
                row["parse_mode"] = balanced.mode.value
                row["canonical_analysis_text"] = balanced.analysis_text
                row["canonical_synthetic_prefix"] = balanced.synthetic_prefix
                row["canonical_synthetic_suffix"] = balanced.synthetic_suffix
                lattice = None
                began = perf_counter()
                signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
                try:
                    _, lattice, result = parse_corpus_case(
                        parser, case,
                        max_items=args.max_items,
                        kbest_work_limit=args.kbest_work_limit,
                    )
                    row["lexical_category_sequence"] = word_category_sequence(lattice)
                    stats = result.stats
                    row.update(compact_stats(stats))
                    row.update({
                        "status": classify(result.completed, stats),
                        "completed": bool(result.completed),
                        "lexical_candidates": len(lattice.candidates),
                        "forest_budget_exceeded": bool(
                            stats.get("budget_exceeded")
                            or (stats.get("dialogue_attempt") or {}).get("budget_exceeded")),
                        "kbest_budget_exceeded": bool(
                            stats.get("kbest_budget_exceeded")
                            or (stats.get("dialogue_attempt") or {}).get(
                                "kbest_budget_exceeded")),
                        "dialogue_attempt": stats.get("dialogue_attempt"),
                        "root_rule": result.best().rule_id if result.completed else None,
                        "dialogue_scoped": bool(stats.get("dialogue_scoped")),
                        "complexity_route": stats.get("complexity_route", "canonical"),
                    })
                except SentenceDeadline:
                    row.update({"status": "timeout", "completed": False})
                except Exception as exc:
                    row.update({
                        "status": "error", "completed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                row["wall_ms"] = round((perf_counter() - began) * 1000, 2)
                if row["status"] != "complete":
                    # A timeout can still retain an already-built lattice.
                    row["lexical_diagnostic"] = (
                        lexical_diagnostics(lattice) if lattice is not None else None
                    )
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                if (index + 1) % 5 == 0 or index + 1 == len(selected):
                    progress = tally(rows)
                    print("NOVEL_DIAGNOSTIC_PROGRESS", json.dumps({
                        "seen": index + 1, "complete": progress["completed"],
                        "statuses": progress["statuses"], "last_ms": row["wall_ms"],
                    }), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)

    canonical_audit, canonical_residuals = canonical_residual_audit(rows)
    with (args.out_dir / "canonical_residuals.jsonl").open(
        "w", encoding="utf8"
    ) as canonical_stream:
        for residual in canonical_residuals:
            canonical_stream.write(json.dumps(residual, ensure_ascii=False) + "\n")
    (args.out_dir / "canonical_residual_audit.json").write_text(
        json.dumps(canonical_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    totals = tally(rows)
    by_band = {band: tally([r for r in rows if r["band"] == band])
               for band, _, _ in BANDS}
    by_book = {
        str(book_id): tally([r for r in rows if r["book_id"] == book_id])
        for book_id in sorted({r["book_id"] for r in rows})
    }
    summary = {
        "schema": "seman2-novel-parse-diagnostics-v5",
        "cohort_sha256": cohort_digest,
        "selection": source_description or (
            "deterministic four-book/four-band complete-utterance sampling with structural roles"
        ),
        "sources": sources,
        "limits": {
            "count": args.count, "max_items": args.max_items,
            "kbest_work_limit": args.kbest_work_limit,
            "deadline_seconds": args.deadline_seconds,
        },
        "totals": totals, "by_band": by_band, "by_book": by_book,
        "canonical_audit": canonical_audit,
        "coverage_percent": round(100 * totals["completed"] / len(rows), 2),
        "elapsed_seconds": round(perf_counter() - started, 2),
        "notes": [
            "Exclusive statuses; independent search-saturation flags.",
            "A structural root does not guarantee a unified valid analysis.",
            "Timeouts and errors are not grammatical coverage failures.",
            "A completed parse can still have an interrupted forest.",
            "Each balanced sentence goes through Parser.parse exactly once.",
            "Full 500-case cohort is exported before parsing begins.",
            "Repeated lexical patterns are exploratory, not causal evidence.",
        ],
    }
    with (args.out_dir / "failed_sentences.jsonl").open(
        "w", encoding="utf8"
    ) as failed_stream:
        for row in rows:
            if row["status"] != "complete":
                failed_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    patterns = recurring_issues(rows)
    (args.out_dir / "recurrent_issues.json").write_text(
        json.dumps(patterns, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    summary["recurrent_issues"] = patterns
    contrasts = contrast_category_patterns(rows)
    (args.out_dir / "pattern_contrasts.json").write_text(
        json.dumps(contrasts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    summary["pattern_contrasts"] = contrasts
    clusters = construction_cluster_audit(rows)
    summary["construction_clusters"] = clusters
    print("NOVEL_GLOBAL_SIGNATURE_AUDIT", json.dumps({
        "conclusive_failures": clusters["total_conclusive_failures"],
        "inconclusive": clusters["total_inconclusive"],
        "failure_percent_by_length_band": clusters["interactions"]["failure_percent_by_length_band"],
        "top_constructions": [
            {key: group[key] for key in (
                "construction", "matched", "successful", "conclusive_failures",
                "conclusive_failure_percent", "failing_case_indices",
                "length_adjusted_expected_failures",
                "length_adjusted_excess_failures",
                "length_adjusted_relative_risk"
            )} for group in clusters["groups"]
            if group["conclusive_failures"] >= 2
        ][:15],
        "top_interactions": clusters["interactions"]["pairs"][:12],
    }, ensure_ascii=False), flush=True)
    (args.out_dir / "construction_clusters.json").write_text(
        json.dumps(clusters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "report.md").write_text(
        render_markdown(summary, rows), encoding="utf8"
    )
    # Small, stable CI-log index: makes failed constructions inspectable even
    # when the uploaded diagnostic artifact is not locally available.
    for row in rows:
        if row["status"] in ("no_structural_root", "roots_without_valid_analysis"):
            print("NOVEL_GRAMMAR_RESIDUAL", json.dumps({
                "index": row["index"], "book_id": row["book_id"],
                "status": row["status"], "sentence": row["sentence"],
                "lexical_category_sequence": row.get("lexical_category_sequence"),
            }, ensure_ascii=False), flush=True)
        if row["status"] in (
            "forest_budget_exceeded", "kbest_budget_exceeded",
            "both_budgets_exceeded", "timeout",
        ):
            print("NOVEL_RESOURCE_LIMIT", json.dumps({
                "index": row["index"], "book_id": row["book_id"],
                "status": row["status"], "sentence": row["sentence"],
                "tokens": row["tokens"], "wall_ms": row["wall_ms"],
                "forest_nodes": row.get("forest_nodes"),
                "structural_root_nodes": row.get("structural_root_nodes"),
                "forest_budget_exceeded": row.get("forest_budget_exceeded"),
                "kbest_budget_exceeded": row.get("kbest_budget_exceeded"),
                "complexity_route": row.get("complexity_route"),
                "lexical_category_sequence": row.get("lexical_category_sequence"),
            }, ensure_ascii=False), flush=True)
    print("NOVEL_DIAGNOSTIC_FINAL", json.dumps({
        "counts": totals, "coverage_percent": summary["coverage_percent"],
        "by_band": by_band, "elapsed_seconds": summary["elapsed_seconds"],
        "recurrent_missing_lexical_words": patterns["word_without_candidate"][:10],
    }, ensure_ascii=False), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir", required=True)
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--max-items", type=int, default=50_000)
    p.add_argument("--kbest-work-limit", type=int, default=500_000)
    p.add_argument("--deadline-seconds", type=float, default=10.0)
    p.add_argument("--out-dir", type=Path, required=True)
    run(p.parse_args())


if __name__ == "__main__":
    main()
