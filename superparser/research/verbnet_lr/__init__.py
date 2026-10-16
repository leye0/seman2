"""Experimental VerbNet 3.4 -> ordered post-verbal prefix hints. No parser mutation."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import json
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class Frame:
    lemma: str
    class_id: str
    symbols: tuple[tuple[str, ...], ...]
    wn_keys: tuple[str, ...]
    offsets: tuple[int, ...]

def compile_xml(path: str | Path, index_sense: str | Path | None = None) -> list[Frame]:
    mapping = {}
    if index_sense:
        for line in Path(index_sense).read_text(encoding="utf8").splitlines():
            fields = line.split()
            if len(fields) > 1 and fields[1].isdigit():
                mapping[fields[0]] = int(fields[1])
    output = []
    def parse_frame(frame):
        syntax = frame.find("SYNTAX")
        if syntax is None:
            return None
        items = []
        verb_found = False
        for node in syntax:
            tag = node.tag
            if tag == "VERB":
                if verb_found: return None
                verb_found = True
            elif not verb_found:
                if tag != "NP": return None
            elif tag == "NP":
                positive = {r.get("type", "") for r in node.findall("./SYNRESTRS/SYNRESTR") if r.get("Value") == "+"}
                kind = "TO_INF" if any("to_inf" in x for x in positive) else "GERUND" if any("ing" in x for x in positive) else "NP"
                items.append((kind,))
            elif tag == "PREP":
                raw = node.get("value", "").replace("|", " ").split()
                items.append(tuple("PREP:" + w.lower() for w in raw) if raw else ("PREP:*",))
            elif tag == "LEX":
                word = node.get("value", "").strip().lower()
                if not word or " " in word: return None
                items.append(("LEX:" + word,))
            elif tag in {"S", "S_INF", "S_ING", "ADJ", "ADV"}:
                items.append(({"S":"CLAUSE", "S_INF":"TO_INF", "S_ING":"GERUND"}.get(tag, tag),))
            else:
                return None
        return tuple(items) if verb_found else None
    def visit(cls, inherited):
        class_id = cls.get("ID", "")
        frames = list(inherited)
        for n, frame in enumerate(cls.findall("./FRAMES/FRAME")):
            compiled = parse_frame(frame)
            if compiled is not None:
                frames.append(compiled)
        for member in cls.findall("./MEMBERS/MEMBER"):
            lemma = member.get("name", "").replace("_", " ").lower()
            if not lemma: continue
            keys = tuple(member.get("wn", "").split())
            offsets = tuple(sorted({mapping[k] for k in keys if k in mapping}))
            for symbols in frames:
                output.append(Frame(lemma, class_id, symbols, keys, offsets))
        for child in cls.findall("./SUBCLASSES/VNSUBCLASS"):
            visit(child, tuple(frames))
    for file in sorted(Path(path).glob("*.xml")):
        root = ET.parse(file).getroot()
        if root.tag == "VNCLASS": visit(root, ())
    return output

class Index:
    """Weak, non-rejecting hints; no forest or exhaustive expansion."""
    def __init__(self, frames):
        self.by_lemma = defaultdict(list)
        for f in frames: self.by_lemma[f.lemma].append(f)
    def predict(self, lemma, observed=(), synset_offset=None):
        candidates = self.by_lemma.get(lemma.lower(), ())
        if synset_offset is not None:
            candidates = [f for f in candidates if synset_offset in f.offsets]
        active = []
        for frame in candidates:
            if len(observed) > len(frame.symbols): continue
            if all(token in choices or (token.startswith("PREP:") and "PREP:*" in choices)
                   for token, choices in zip(observed, frame.symbols)):
                active.append(frame)
        next_expected = sorted({t for f in active if len(observed) < len(f.symbols)
                                for t in f.symbols[len(observed)]})
        completed = any(len(observed) == len(f.symbols) for f in active)
        return {"status": "ATTESTED" if completed else "PREFIX" if active else "UNKNOWN",
                "next_events": next_expected, "frames": len(active)}

def predict_candidate(index, candidate, observed=()):
    """Candidate keeps Seman2 morphology and shared lexical alternatives unchanged."""
    if candidate.category != "V": return {"status":"UNKNOWN", "next_events":[], "frames":0}
    import re
    offsets = {int(m.group(1)) for key in candidate.sense_ids
               if (m := re.fullmatch(r"wn-(\\d+)-v-(?:finite|base|ed|ing)", key))}
    if not offsets: return index.predict(candidate.lemma, tuple(observed))
    results = [index.predict(candidate.lemma, tuple(observed), offset) for offset in sorted(offsets)]
    return {"status": "ATTESTED" if any(r["status"]=="ATTESTED" for r in results)
            else "PREFIX" if any(r["status"]=="PREFIX" for r in results) else "UNKNOWN",
            "next_events": sorted({x for r in results for x in r["next_events"]}),
            "frames":sum(r["frames"] for r in results)}
