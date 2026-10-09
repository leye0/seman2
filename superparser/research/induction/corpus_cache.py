"""Persistent, content-addressed corpus parsing cache for induction experiments."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping, Sequence

from seman_parser import FeatureStructure, Mention, Parser, __version__
from seman_parser.coverage import _NOISE, _split_sentences
from seman_parser.mentions import extract_event_mentions, extract_mentions
from seman_parser.refdetect import detect_all

from .observation_graph import ObservationGraph, parse_to_observation


CACHE_SCHEMA = "induction-corpus-cache/0.1"
SPLITTER_VERSION = "line-prefix-sentences/0.1"


@dataclass(frozen=True, slots=True)
class CorpusCase:
    index: int
    source_line: int
    text: str
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "source_line": self.source_line,
            "text": self.text,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class CachedObservation:
    case: CorpusCase
    graph: ObservationGraph
    mentions: tuple[Mention, ...]
    selected_goal: str
    parse_ms: float
    cache_hit: bool
    dropped_reference_links: int = 0


@dataclass(frozen=True, slots=True)
class CorpusCacheReport:
    cache_path: Path
    fingerprint: str
    observations: tuple[CachedObservation, ...]
    hits: int
    misses: int


def extract_line_prefix_cases(
    path: str | Path,
    *,
    line_limit: int,
    include_headers: bool = True,
) -> list[CorpusCase]:
    """Split only the requested physical line prefix, preserving line origin."""
    path = Path(path)
    cases: list[CorpusCase] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines()[:line_limit],
        start=1,
    ):
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        header = bool(
            line.isupper() or re.match(r"^(?:PART|CHAPTER)\b", line, re.IGNORECASE)
        )
        if header and not include_headers:
            continue
        pieces = [line] if header else _split_sentences(line)
        for piece in pieces:
            text = piece.strip().strip("\"'“”‘’")
            if len(text) < 2 or _NOISE.match(text):
                continue
            cases.append(
                CorpusCase(
                    index=len(cases),
                    source_line=line_number,
                    text=text,
                    kind="header" if header else "sentence",
                )
            )
    return cases


def corpus_cache_fingerprint(
    corpus_path: str | Path,
    *,
    data_dir: str | Path,
    line_limit: int,
    antecedent_window: int,
    case_limit: int | None = None,
    source_root: str | Path | None = None,
) -> str:
    corpus_path = Path(corpus_path)
    data_dir = Path(data_dir)
    source_root = Path(source_root) if source_root else Path(__file__).resolve().parents[2]
    digest = sha256()
    digest.update(CACHE_SCHEMA.encode())
    digest.update(SPLITTER_VERSION.encode())
    digest.update(__version__.encode())
    digest.update(str(line_limit).encode())
    digest.update(str(case_limit).encode())
    digest.update(str(antecedent_window).encode())
    prefix = corpus_path.read_text(encoding="utf-8").splitlines(keepends=True)[:line_limit]
    digest.update("".join(prefix).encode("utf-8"))
    resource_names = ("grammar.jsonl", "function_words.jsonl", "types.json", "wordnet_path")
    for name in resource_names:
        candidate = data_dir / name
        if candidate.exists():
            digest.update(name.encode())
            digest.update(candidate.read_bytes())
    for directory in (source_root / "seman_parser", source_root / "research" / "induction"):
        for candidate in sorted(directory.glob("*.py")):
            digest.update(candidate.name.encode())
            digest.update(candidate.read_bytes())
    return digest.hexdigest()


class CorpusGraphCache:
    def __init__(
        self,
        *,
        cache_dir: str | Path,
        data_dir: str | Path,
        antecedent_window: int = 3,
    ) -> None:
        if antecedent_window < 0:
            raise ValueError("antecedent_window must be non-negative")
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.antecedent_window = antecedent_window

    def load_or_build(
        self,
        corpus_path: str | Path,
        *,
        line_limit: int,
        case_limit: int | None = None,
    ) -> CorpusCacheReport:
        corpus_path = Path(corpus_path)
        cases = extract_line_prefix_cases(corpus_path, line_limit=line_limit)
        if case_limit is not None:
            if case_limit < 1:
                raise ValueError("case_limit must be positive")
            cases = cases[:case_limit]
        fingerprint = corpus_cache_fingerprint(
            corpus_path,
            data_dir=self.data_dir,
            line_limit=line_limit,
            antecedent_window=self.antecedent_window,
            case_limit=case_limit,
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        scope = f"lines-{line_limit}"
        if case_limit is not None:
            scope += f"-cases-{case_limit}"
        cache_path = self.cache_dir / f"{corpus_path.stem}-{scope}-{fingerprint[:16]}.jsonl"
        cached = self._read(cache_path, fingerprint)
        parser = Parser.from_dir(self.data_dir, cache_size=0)
        np_parser = Parser(parser.resources, goal_category="NP", cache_size=0)
        observations: list[CachedObservation] = []
        mention_history: list[Mention] = []
        hits = 0
        misses = 0

        if not cache_path.exists():
            cache_path.write_text(
                _json(
                    {
                        "type": "header",
                        "schema_version": CACHE_SCHEMA,
                        "fingerprint": fingerprint,
                        "line_limit": line_limit,
                        "case_limit": case_limit,
                        "antecedent_window": self.antecedent_window,
                        "case_count": len(cases),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

        for case in cases:
            key = self._case_key(fingerprint, case)
            row = cached.get(key)
            if row is not None:
                graph = ObservationGraph.from_dict(row["graph"])
                mentions = tuple(_mention_from_dict(value) for value in row["mentions"])
                selected_goal = str(row["selected_goal"])
                parse_ms = float(row["parse_ms"])
                dropped_reference_links = int(row.get("dropped_reference_links", 0))
                hit = True
                hits += 1
            else:
                started = time.perf_counter()
                report = parser.parse(case.text)
                selected_goal = "CLAUSE"
                if not report.result.completed:
                    np_report = np_parser.parse(case.text)
                    if np_report.result.completed:
                        report = np_report
                        selected_goal = "NP"
                best = report.result.best()
                mentions = ()
                links = ()
                dropped_reference_links = 0
                if best is not None:
                    mentions = tuple(
                        extract_mentions(best, case.index)
                        + extract_event_mentions(best, case.index)
                    )
                    earliest = case.index - self.antecedent_window
                    antecedents = tuple(
                        mention
                        for mention in mention_history
                        if mention.sentence_index >= earliest
                    )
                    links = tuple(
                        detect_all(
                            best,
                            mentions,
                            sentence_index=case.index,
                            parse_id=f"line-{case.source_line}",
                            antecedents=antecedents,
                            text=case.text,
                        ).links
                    )
                    mention_ids = {
                        mention.mention_id for mention in (*antecedents, *mentions)
                    }
                    dropped_reference_links = sum(
                        link.source not in mention_ids for link in links
                    )
                    links = tuple(
                        link for link in links if link.source in mention_ids
                    )
                catalog = {
                    mention.mention_id: mention
                    for mention in (*mention_history, *mentions)
                }
                graph = parse_to_observation(
                    report.result,
                    parser_version=__version__,
                    mentions=mentions,
                    reference_links=links,
                    mention_catalog=catalog,
                )
                parse_ms = (time.perf_counter() - started) * 1000
                payload = {
                    "type": "observation",
                    "key": key,
                    "case": case.as_dict(),
                    "selected_goal": selected_goal,
                    "parse_ms": round(parse_ms, 6),
                    "dropped_reference_links": dropped_reference_links,
                    "mentions": [mention.as_dict() for mention in mentions],
                    "graph": graph.as_dict(),
                }
                with cache_path.open("a", encoding="utf-8") as handle:
                    handle.write(_json(payload) + "\n")
                    handle.flush()
                hit = False
                misses += 1
            mention_history.extend(mentions)
            observations.append(
                CachedObservation(
                    case,
                    graph,
                    mentions,
                    selected_goal,
                    parse_ms,
                    hit,
                    dropped_reference_links,
                )
            )
        return CorpusCacheReport(
            cache_path,
            fingerprint,
            tuple(observations),
            hits,
            misses,
        )

    @staticmethod
    def _case_key(fingerprint: str, case: CorpusCase) -> str:
        return sha256(
            f"{fingerprint}\0{case.index}\0{case.source_line}\0{case.text}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _read(cache_path: Path, fingerprint: str) -> dict[str, dict[str, Any]]:
        if not cache_path.exists():
            return {}
        found: dict[str, dict[str, Any]] = {}
        with cache_path.open(encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    # An interrupted final append is safely recomputed.
                    continue
                if line_number == 1:
                    if row.get("fingerprint") != fingerprint:
                        return {}
                    continue
                if row.get("type") == "observation" and isinstance(row.get("key"), str):
                    found[row["key"]] = row
        return found


def _mention_from_dict(row: Mapping[str, Any]) -> Mention:
    return Mention(
        mention_id=str(row["id"]),
        surface=str(row["surface"]),
        span=(int(row["span"][0]), int(row["span"][1])),
        kind=str(row["kind"]),
        sentence_index=int(row["sentence"]),
        features=FeatureStructure.build(row.get("features", {})),
        semantic_type=row.get("semantic_type"),
        node_id=row.get("node_id"),
        head_lemma=row.get("head_lemma"),
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
