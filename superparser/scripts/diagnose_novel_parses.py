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
from pathlib import Path
import signal
from time import perf_counter

from scripts.corpus_samples import BANDS, choose_cases, sample_spread
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]
# Fixed 500-case reference, computed from cohort.jsonl on the initial run.
# Any altered sentence segmentation or sampling must be reviewed explicitly.
EXPECTED_500_COHORT_SHA256 = "cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a"
STATUSES = (
    "complete", "both_budgets_exceeded", "forest_budget_exceeded",
    "kbest_budget_exceeded", "no_structural_root",
    "roots_without_valid_analysis", "timeout", "error",
)
MEANINGS = {
    "complete": "Best grammatical analysis certified",
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
    forest = bool(stats.get("budget_exceeded"))
    kbest = bool(stats.get("kbest_budget_exceeded"))
    if forest and kbest:
        return "both_budgets_exceeded"
    if forest:
        return "forest_budget_exceeded"
    if kbest:
        return "kbest_budget_exceeded"
    if int(stats.get("structural_root_nodes", 0)) == 0:
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
        word = any(ch.isalpha() for ch in token.text)
        rows.append({
            "index": token.index, "surface": token.text,
            "span": [token.start, token.end], "is_word": word,
            "categories": sorted({c.category for c in exact}),
            "candidate_count": len(exact), "multiword_cover_count": len(covering),
            "no_exact_candidate": word and not exact,
            "no_candidate_or_cover": word and not exact and not covering,
            "candidates": [detail(c) for c in exact],
            "covering_multiword_candidates": [detail(c) for c in covering],
        })
    return {
        "schema": "seman2-failed-sentence-lexicon-v1",
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
    return [
        "/".join(sorted(categories.get((token.start, token.end), ())))
        or "NO_EXACT_LEXICAL_CANDIDATE"
        for token in lattice.tokens if any(ch.isalpha() for ch in token.text)
    ]


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
        "schema": "seman2-novel-contrastive-patterns-v1",
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


def run(args: argparse.Namespace) -> dict:
    if args.max_items < 1 or args.kbest_work_limit < 1 or args.deadline_seconds <= 0:
        raise ValueError("Budgets and deadline must be positive")
    selected, sources = select_cases(args.count)
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
    if args.count == 500 and cohort_digest != EXPECTED_500_COHORT_SHA256:
        raise ValueError(
            "The fixed 500-case reference cohort changed: "
            f"expected {EXPECTED_500_COHORT_SHA256}, got {cohort_digest}. "
            "Review corpus extraction/sampling changes before updating the pin."
        )
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=args.wordnet_dir)
    parser = Parser(resources, cache_size=0, max_items=args.max_items)
    # Warm lexical lookup before any per-sentence deadline.
    build_lattice("John opened the box.", resources.lexicon, multiword_max=1)
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
                    "semicolon_split": bool(case.get("semicolon_split")),
                    "synthetic_prefix": case.get("synthetic_prefix", ""),
                    "synthetic_suffix": case.get("synthetic_suffix", ""),
                    "synthetic_terminal": bool(case.get("synthetic_terminal")),
                    "case_id": str(case["book_id"]) + ":" + sha256(
                        source_text.encode("utf8")
                    ).hexdigest()[:16],
                    "sha256": sha256(case["text"].encode("utf8")).hexdigest(),
                }
                lattice = None
                began = perf_counter()
                signal.setitimer(signal.ITIMER_REAL, args.deadline_seconds)
                try:
                    lattice = build_lattice(
                        case["text"], resources.lexicon, multiword_max=1
                    )
                    row["lexical_category_sequence"] = word_category_sequence(lattice)
                    result = parser.parse_grammar_lattice(
                        lattice, max_items=args.max_items,
                        kbest_work_limit=args.kbest_work_limit,
                    )
                    stats = result.stats
                    row.update(compact_stats(stats))
                    row.update({
                        "status": classify(result.completed, stats),
                        "completed": bool(result.completed),
                        "lexical_candidates": len(lattice.candidates),
                        "forest_budget_exceeded": bool(stats.get("budget_exceeded")),
                        "kbest_budget_exceeded": bool(stats.get("kbest_budget_exceeded")),
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

    totals = tally(rows)
    by_band = {band: tally([r for r in rows if r["band"] == band])
               for band, _, _ in BANDS}
    by_book = {
        str(book_id): tally([r for r in rows if r["book_id"] == book_id])
        for book_id in sorted({r["book_id"] for r in rows})
    }
    summary = {
        "schema": "seman2-novel-parse-diagnostics-v3",
        "cohort_sha256": cohort_digest,
        "selection": "deterministic four-book/four-band cleaned Gutenberg sample",
        "sources": sources,
        "limits": {
            "count": args.count, "max_items": args.max_items,
            "kbest_work_limit": args.kbest_work_limit,
            "deadline_seconds": args.deadline_seconds,
        },
        "totals": totals, "by_band": by_band, "by_book": by_book,
        "coverage_percent": round(100 * totals["completed"] / len(rows), 2),
        "elapsed_seconds": round(perf_counter() - started, 2),
        "notes": [
            "Exclusive statuses; independent search-saturation flags.",
            "A structural root does not guarantee a unified valid analysis.",
            "Timeouts and errors are not grammatical coverage failures.",
            "A completed parse can still have an interrupted forest.",
            "Each sentence is parsed once, without A/B comparisons.",
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
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.out_dir / "report.md").write_text(
        render_markdown(summary, rows), encoding="utf8"
    )
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
