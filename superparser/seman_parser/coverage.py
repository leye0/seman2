"""Coverage harness over a real corpus (the NLP novel).

Extracts sentences, parses each one, and reports what the current
grammar/lexicon can and cannot handle. Used as a regression corpus and
as a source of new linguistic phenomena to cover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .engine import Parser
from .sentence_boundaries import has_final_punctuation, split_prose_sentences

_NOISE = re.compile(r"^[\s\"'“”‘’\-–—*•>]*$")
# Abbreviations that end with a period but do not end a sentence.
_ABBREV = re.compile(
    r"\b(?:Mr|Ms|Mrs|Dr|Prof|Sr|Jr|St|No|vs|etc|approx|Fig|Vol|Ch|cf|e\.g|i\.e)\.$"
)


@dataclass(frozen=True, slots=True)
class SentenceCase:
    index: int
    text: str
    source_line: int


@dataclass
class CaseResult:
    case: SentenceCase
    completed: bool
    category: str | None
    rule_id: str | None
    relations: tuple[str, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.case.index,
            "text": self.case.text,
            "completed": self.completed,
            "category": self.category,
            "rule_id": self.rule_id,
            "relations": list(self.relations),
            "error": self.error,
        }


@dataclass
class CoverageReport:
    results: tuple[CaseResult, ...]
    total: int = 0
    completed: int = 0
    failures: tuple[CaseResult, ...] = ()
    successes: tuple[CaseResult, ...] = ()
    by_rule: dict[str, int] = field(default_factory=dict)
    by_relation: dict[str, int] = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return (self.completed / self.total) if self.total else 0.0

    def summary(self) -> str:
        lines = [
            f"sentences: {self.total}",
            f"parsed:    {self.completed} ({self.rate:.1%})",
            f"failed:    {len(self.failures)}",
            "",
            "top rules:",
        ]
        for rule, count in sorted(self.by_rule.items(), key=lambda kv: -kv[1])[:12]:
            lines.append(f"  {count:4d}  {rule}")
        lines.append("")
        lines.append("top relations:")
        for rel, count in sorted(self.by_relation.items(), key=lambda kv: -kv[1])[:12]:
            lines.append(f"  {count:4d}  {rel}")
        return "\n".join(lines)

    def failure_samples(self, limit: int = 20) -> list[str]:
        return [r.case.text for r in self.failures[:limit]]



_ABBREV_TOKEN = re.compile(
    r"(?:Mr|Ms|Mrs|Dr|Prof|Sr|Jr|St|No|vs|etc|approx|Fig|Vol|Ch|cf)\.$"
)


def _split_sentences(line: str) -> list[str]:
    """Lossless dialogue-aware splitter shared with the novel extractor."""
    return split_prose_sentences(line)


def extract_sentences(path: str | Path, *, limit: int | None = None) -> list[SentenceCase]:
    """Split a text file into sentence cases, skipping headers and noise."""
    path = Path(path)
    sentences: list[SentenceCase] = []
    index = 0
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        if ((line.isupper() and not has_final_punctuation(line)) or re.match(
                r"^(?:PART|CHAPTER)\s+(?:[IVXLCDM]+|\d+)\b", line, re.I
        )):
            continue
        if line.startswith("#"):
            continue
        for piece in _split_sentences(line):
            piece = piece.strip()
            if not re.search(r"[A-Za-z]", piece) or _NOISE.match(piece):
                continue
            # Drop sentence fragments that are only an abbreviation + name.
            if _ABBREV.search(piece) and len(piece.split()) <= 3:
                continue
            # Keep only pieces that look like a sentence.
            if not has_final_punctuation(piece) and len(piece) > 200:
                continue
            sentences.append(SentenceCase(index=index, text=piece, source_line=line_no))
            index += 1
            if limit is not None and index >= limit:
                return sentences
    return sentences


def run_coverage(
    corpus_path: str | Path,
    *,
    data_dir: str | Path,
    limit: int | None = None,
    goal_category: str = "CLAUSE",
) -> CoverageReport:
    """Parse every sentence case and aggregate statistics."""
    # Corpus sentences are unique, so retaining every packed forest in the
    # normal interactive parse cache only grows memory without producing a
    # cache hit (hundreds of sentences can otherwise consume gigabytes).
    parser = Parser.from_dir(data_dir, goal_category=goal_category, cache_size=0)
    cases = extract_sentences(corpus_path, limit=limit)
    results: list[CaseResult] = []
    by_rule: dict[str, int] = {}
    by_relation: dict[str, int] = {}
    completed = 0

    for case in cases:
        try:
            report = parser.parse(case.text)
            best = report.result.best()
            ok = report.result.completed
            if not ok:
                # Fragments (titles, NPs) are legitimate analyses when the
                # NP goal succeeds even if CLAUSE does not.
                from .engine import Parser as _P
                np_parser = _P(parser.resources, goal_category="NP")
                if np_parser.parse(case.text).result.completed:
                    ok = True
            rule_id = best.rule_id if best else None
            category = best.category if best else None
            semantic = report.interpret(best) if best else None
            relations = tuple(sorted({e.relation for e in semantic.graph.relations})) if semantic else ()
            result = CaseResult(
                case=case,
                completed=ok,
                category=category,
                rule_id=rule_id,
                relations=relations,
            )
        except Exception as exc:  # noqa: BLE001 — coverage harness must survive
            result = CaseResult(
                case=case,
                completed=False,
                category=None,
                rule_id=None,
                relations=(),
                error=f"{type(exc).__name__}: {exc}",
            )
        results.append(result)
        if result.completed:
            completed += 1
            if result.rule_id:
                by_rule[result.rule_id] = by_rule.get(result.rule_id, 0) + 1
            for rel in result.relations:
                by_relation[rel] = by_relation.get(rel, 0) + 1

    failures = tuple(r for r in results if not r.completed)
    successes = tuple(r for r in results if r.completed)
    return CoverageReport(
        results=tuple(results),
        total=len(results),
        completed=completed,
        failures=failures,
        successes=successes,
        by_rule=by_rule,
        by_relation=by_relation,
    )
