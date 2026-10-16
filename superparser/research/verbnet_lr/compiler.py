"""Compile VerbNet 3.4 XML into a compact, read-only left-to-right valency index.

This is intentionally a *hint* layer, not a parser or rejection validator:
VerbNet frames are not an exhaustive grammar. Unknown patterns stay UNKNOWN.
Lexical morphology and WordNet sense identities remain owned by Seman2.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import re
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class Frame:
    lemma: str
    class_id: str
    frame_id: str
    symbols: tuple[tuple[str, ...], ...]  # ordered post-VERB event alternatives
    roles: tuple[str, ...]                # roles for the events (no semantic inference)
    wordnet_keys: tuple[str, ...]         # original VerbNet sense keys
    wordnet_offsets: tuple[int, ...]      # exact index.sense joins, if available
    link: str                             # exact, unresolved, or lemma_only

    def as_dict(self) -> dict:
        return {"lemma": self.lemma, "class": self.class_id, "id": self.frame_id,
                "symbols": [list(x) for x in self.symbols], "roles": list(self.roles),
                "wn_keys": list(self.wordnet_keys), "wn_offsets": list(self.wordnet_offsets),
                "link": self.link}

    @classmethod
    def from_dict(cls, raw: Mapping) -> "Frame":
        return cls(str(raw["lemma"]), str(raw["class"]), str(raw["id"]),
                   tuple(tuple(x) for x in raw["symbols"]), tuple(raw["roles"]),
                   tuple(raw.get("wn_keys", ())), tuple(int(x) for x in raw.get("wn_offsets", ())),
                   str(raw.get("link", "unresolved")))


def sense_offsets(path: str | Path) -> dict[str, int]:
    """Read WordNet 3.0 index.sense (sense key -> synset offset)."""
    result = {}
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                result[parts[0]] = int(parts[1])
    return result


def _prep_options(value: str) -> tuple[str, ...]:
    """VerbNet PREP values encode alternatives with spaces or '|' separators."""
    value = value.casefold().strip()
    if not value:
        return ("PREP:*",)  # underspecified, never a specific-preposition assertion
    words = tuple(dict.fromkeys(re.split(r"\s*\|\s*|\s+", value)))
    return tuple("PREP:" + word for word in words if word)


def _np_event(node: ET.Element) -> str:
    positive = {r.get("type", "").lower() for r in node.findall("./SYNRESTRS/SYNRESTR")
                if r.get("Value") == "+"}
    if any("to_inf" in r for r in positive):
        return "TO_INF"
    if any("ing" in r for r in positive):
        return "GERUND"
    if any("that_comp" in r or "sentential" in r for r in positive):
        return "CLAUSE"
    return "NP"


def _compile_syntax(node: ET.Element) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]] | None:
    symbols: list[tuple[str, ...]] = []
    roles: list[str] = []
    found_verb = False
    for element in node:
        tag = element.tag.upper()
        if tag == "VERB":
            if found_verb:
                return None
            found_verb = True
            continue
        if tag == "NP":
            # The initial NP is the syntactic subject; it is not a post-verb obligation.
            if not found_verb:
                continue
            symbols.append((_np_event(element),))
            roles.append(element.get("value", ""))
        elif tag == "PREP" and found_verb:
            symbols.append(_prep_options(element.get("value", "")))
            roles.append("")
        elif tag == "LEX" and found_verb:
            word = element.get("value", "").strip().casefold()
            if not word or " " in word:
                return None
            symbols.append(("LEX:" + word,))
            roles.append("")
        elif found_verb and tag in {"ADJ", "ADV", "S", "S_INF", "S_ING", "S_ING_SC", "S_ING_OC"}:
            mapping = {"S": "CLAUSE", "S_INF": "TO_INF", "S_ING": "GERUND",
                       "S_ING_SC": "GERUND", "S_ING_OC": "GERUND"}
            symbols.append((mapping.get(tag, tag),))
            roles.append(element.get("value", ""))
        else:
            # Unsupported syntax must not be silently shortened to a valid frame.
            return None
    return (tuple(symbols), tuple(roles)) if found_verb else None


def compile_directory(xml_dir: str | Path, wordnet_sense_index: str | Path | None = None
                      ) -> tuple[tuple[Frame, ...], dict]:
    """Compile nested subclasses with inherited *ancestor* frames only.

    Member ownership matters: parent members do not gain child-only frames.
    Does not download or redistribute the original VerbNet XML.
    """
    xml_dir = Path(xml_dir)
    if not xml_dir.is_dir():
        raise FileNotFoundError(xml_dir)
    offsets = sense_offsets(wordnet_sense_index) if wordnet_sense_index else {}
    stats = Counter()
    compiled: list[Frame] = []

    def walk(node: ET.Element, inherited: tuple[tuple[str, tuple[tuple[str, ...], ...], tuple[str, ...]], ...]):
        class_id = node.get("ID", "")
        available = list(inherited)
        for n, frame in enumerate(node.findall("./FRAMES/FRAME")):
            stats["frames_seen"] += 1
            syntax = frame.find("SYNTAX")
            parsed = _compile_syntax(syntax) if syntax is not None else None
            if parsed is None:
                stats["frames_unsupported"] += 1
                continue
            available.append((f"{class_id}:{n}", *parsed))
        for member in node.findall("./MEMBERS/MEMBER"):
            lemma = member.get("name", "").casefold().replace("_", " ")
            if not lemma:
                continue
            keys = tuple(k for k in member.get("wn", "").split() if k)
            mapped = tuple(sorted({offsets[k] for k in keys if k in offsets}))
            link = "exact" if mapped else ("unresolved" if keys else "lemma_only")
            stats["members"] += 1
            if link == "exact":
                stats["members_exact"] += 1
            for frame_id, symbols, roles in available:
                compiled.append(Frame(lemma, class_id, frame_id, symbols, roles, keys, mapped, link))
        for child in node.findall("./SUBCLASSES/VNSUBCLASS"):
            walk(child, tuple(available))

    files = sorted(xml_dir.glob("*.xml"))
    for xml_file in files:
        stats["xml_files"] += 1
        root = ET.parse(xml_file).getroot()
        if root.tag != "VNCLASS":
            stats["unexpected_roots"] += 1
            continue
        walk(root, ())
    # The same lemma may inherit the same frame via more than one membership.
    unique = { (f.lemma, f.class_id, f.frame_id, f.symbols, f.wordnet_keys): f for f in compiled }
    frames = tuple(sorted(unique.values(), key=lambda f: (f.lemma, f.class_id, f.frame_id)))
    stats["compiled_frames"] = len(frames)
    stats["lemmas"] = len({f.lemma for f in frames})
    return frames, dict(stats)


def write_index(path: str | Path, frames: Iterable[Frame], stats: Mapping | None = None) -> None:
    """Write a portable index; .gz uses deterministic small gzip packaging."""
    payload = {"schema": 1, "source": "VerbNet 3.4", "stats": dict(stats or {}),
               "frames": [frame.as_dict() for frame in frames]}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if str(path).endswith(".gz"):
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as output:
            output.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def read_index(path: str | Path) -> "PrefixIndex":
    if str(path).endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as source:
            payload = json.load(source)
    else:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError("unsupported VerbNet index schema")
    return PrefixIndex(tuple(Frame.from_dict(row) for row in payload["frames"]))


@dataclass(frozen=True, slots=True)
class Prediction:
    status: str                       # ATTESTED, PREFIX, or UNKNOWN; NEVER "invalid"
    next_events: tuple[str, ...]
    matching_frames: tuple[Frame, ...]
    complete_frames: tuple[Frame, ...]


class _State:
    __slots__ = ("edges", "reachable", "complete")

    def __init__(self):
        self.edges: dict[str, _State] = {}
        self.reachable: set[int] = set()
        self.complete: set[int] = set()


class PrefixIndex:
    """Shared *prefix trie*, not a packed parse forest. Built lazily per lemma.

    Runs on category/lexical events AFTER the verb (NP, PREP:to, TO_INF, ...).
    It provides positive hints. Missing data cannot reject an analysis.
    """
    def __init__(self, frames: Iterable[Frame]):
        by_lemma: dict[str, list[Frame]] = defaultdict(list)
        for frame in frames:
            by_lemma[frame.lemma].append(frame)
        self._frames = {lemma: tuple(items) for lemma, items in by_lemma.items()}
        self._tries: dict[str, _State] = {}

    def lemmas(self) -> int:
        return len(self._frames)

    def _root(self, lemma: str) -> _State:
        if lemma in self._tries:
            return self._tries[lemma]
        root = _State()
        for frame_id, frame in enumerate(self._frames.get(lemma, ())):
            states = [root]
            root.reachable.add(frame_id)
            for options in frame.symbols:
                next_states = []
                for state in states:
                    for option in options:
                        child = state.edges.setdefault(option, _State())
                        child.reachable.add(frame_id)
                        next_states.append(child)
                states = next_states
            for state in states:
                state.complete.add(frame_id)
        self._tries[lemma] = root
        return root

    @staticmethod
    def _eligible(frame: Frame, synset_offset: int | None) -> bool:
        # If the caller knows a WordNet synset, a VerbNet sense-key match is
        # required for high-confidence hints. Other frames remain unverified.
        return synset_offset is None or (frame.link == "exact" and synset_offset in frame.wordnet_offsets)

    def predict(self, lemma: str, observed: Iterable[str] = (), *,
                synset_offset: int | None = None) -> Prediction:
        lemma = lemma.casefold().replace("_", " ")
        frames = self._frames.get(lemma, ())
        states = (self._root(lemma),)
        for event in observed:
            event = event.strip()
            next_states = {}
            for state in states:
                # Explicit and wildcard edges are *both* compatible.
                keys = (event, "PREP:*") if event.startswith("PREP:") and event != "PREP:*" else (event,)
                for key in keys:
                    child = state.edges.get(key)
                    if child is not None:
                        next_states[id(child)] = child
            if not next_states:
                return Prediction("UNKNOWN", (), (), ())
            states = tuple(next_states.values())
        all_ids = set().union(*(state.reachable for state in states))
        ids = sorted(i for i in all_ids if self._eligible(frames[i], synset_offset))
        if not ids:
            return Prediction("UNKNOWN", (), (), ())
        eligible = set(ids)
        matches = tuple(frames[i] for i in ids)
        complete_ids = set().union(*(state.complete for state in states)) & eligible
        complete = tuple(frames[i] for i in sorted(complete_ids))
        next_events = tuple(sorted({key for state in states for key, node in state.edges.items()
                                    if node.reachable & eligible}))
        return Prediction("ATTESTED" if complete else "PREFIX", next_events, matches, complete)
