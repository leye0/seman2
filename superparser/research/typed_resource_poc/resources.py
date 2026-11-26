"""Pinned external grammatical resources; never mine the Novel test corpus.

Only source inventories are stored in CI artifacts. Licensed corpora themselves
are downloaded at runtime and are not committed or redistributed.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
import gzip
import io
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ERG_COMMIT = "13b615ab607374ed7cafe753830e23043a22b71d"
UD_COMMIT = "491be069d36e378f67c29f183699eea88308ea42"
FRAMENET_SHA256 = "22f6aad6fb799ba4dbed0440714e1118442ad7d7345351de37428581284f471c"
WORDNET_SHA256 = "cbda5ea6eef7f36a97a43d4a75f85e07fccbb4f23657d27b4ccbc93e2646ab59"
SOURCES = {
    "ERG": {"url": f"https://github.com/delph-in/erg/tree/{ERG_COMMIT}", "license": "MIT"},
    "UD_EWT": {"url": f"https://github.com/UniversalDependencies/UD_English-EWT/tree/{UD_COMMIT}",
               "license": "CC-BY-SA-4.0"},
    "FrameNet": {"url": "https://github.com/nltk/nltk_data/tree/gh-pages/packages/corpora/framenet_v17.zip",
                 "license": "CC-BY-3.0"},
    "WordNet": {"url": "https://github.com/nltk/nltk_data/tree/gh-pages/packages/corpora/wordnet.zip",
                "license": "WordNet-3.0"},
    "VerbNet": {"url": "superparser/research/verbnet_lr/verbnet34.compiled.json.gz",
                "license": "see-existing-repository-provenance"},
}


def download(url: str, destination: Path, sha: str | None = None) -> bytes:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        payload = destination.read_bytes()
        if sha is None or sha256(payload).hexdigest() == sha:
            return payload
    request = Request(url, headers={"User-Agent": "seman2-typed-resource-poc/0.1"})
    with urlopen(request, timeout=180) as stream:
        payload = stream.read()
    if sha and sha256(payload).hexdigest() != sha:
        raise ValueError("External source checksum mismatch: " + url)
    destination.write_bytes(payload)
    return payload


def load_erg(base: Path) -> dict:
    """A conservative lexical inventory and type graph extracted from ERG TDL.

    This does NOT interpret all TDL constraints or claim to be an ERG parser.
    The original lexical type names are preserved, with raw ancestors when
    detectable. The lexical type cannot be substituted for a valence claim.
    """
    prefix = f"https://raw.githubusercontent.com/delph-in/erg/{ERG_COMMIT}/"
    lexicon = download(prefix + "lexicon.tdl", base / "erg-lexicon.tdl").decode("utf-8")
    types_text = download(prefix + "lextypes.tdl", base / "erg-lextypes.tdl").decode("utf-8")
    types = {}
    for line in types_text.splitlines():
        m = re.match(r"^([\w-]+)\s*:=\s*([^.;]+)", line)
        if not m:
            continue
        parents = re.findall(r"\b([\w-]+)\b", m.group(2).split("[")[0])
        types[m.group(1)] = parents[:12]
    # TDL lexical definitions begin at the start of a line.
    start = list(re.finditer(r"(?m)^([\w-]+)\s*:=\s*([\w-]+)\s*&", lexicon))
    entries = defaultdict(set)
    sampled = []
    for i, m in enumerate(start):
        block = lexicon[m.end(): start[i+1].start() if i+1 < len(start) else len(lexicon)]
        # Stem and orthography declarations are robust to whitespace and casing.
        stems = re.findall(r"(?is)\b(?:STEM|ORTH)\s*<\s*\"([^\"]+)\"", block)
        if stems:
            for stem in stems[:4]:
                if len(stem.split()) == 1:
                    entries[stem.casefold()].add(m.group(2))
            if len(sampled) < 4:
                sampled.append({"entry": m.group(1), "type": m.group(2), "stems": stems[:3]})
    return {"lexicon_entries_detected": len(start), "lexicon_stems": len(entries),
            "lexicon_samples": sampled, "types": types,
            "lexemes": {k: sorted(v) for k,v in entries.items()}}


def load_framenet(base: Path) -> dict:
    url = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/framenet_v17.zip"
    archive = download(url, base / "framenet_v17.zip", FRAMENET_SHA256)
    with ZipFile(io.BytesIO(archive)) as z:
        matches = [name for name in z.namelist() if name.endswith("/luIndex.xml")]
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one FrameNet lexical-unit index")
        root = ET.fromstring(z.read(matches[0]))
    frames = defaultdict(set)
    for node in root.iter():
        attrs = node.attrib
        name = attrs.get("name", "")
        frame = attrs.get("frameName")
        if frame and "." in name:
            lemma, pos = name.rsplit(".",1)
            frames[(lemma.casefold(), pos)].add(frame)
    return {"lexical_units": len(list(root)), "entries": len(frames),
            "frames": {f"{lemma}|{pos}": sorted(items) for (lemma,pos),items in frames.items()}}


def load_verbnet(compiled: Path) -> dict:
    """Index the existing VerbNet 3.4 compilation by lemma and class ID.

    The packaged schema is `{"frames": [{"lemma": ..., "class": ...,
    "symbols": ..., "roles": ...}, ...]}`. Do not interpret its frames as
    nested VerbNet XML members or invent class names when evidence is absent.
    """
    with gzip.open(compiled, "rt", encoding="utf-8") as source:
        root = json.load(source)
    if not isinstance(root, dict) or not isinstance(root.get("frames"), list):
        raise ValueError("Unexpected compiled VerbNet frame schema")
    matches: dict[str, set[str]] = defaultdict(set)
    valid_frames = 0
    for row in root["frames"]:
        if not isinstance(row, dict):
            raise ValueError("Non-object in compiled VerbNet frames")
        lemma, class_id = row.get("lemma"), row.get("class")
        if not isinstance(lemma, str) or not lemma.strip():
            raise ValueError("VerbNet frame without lexical lemma")
        if not isinstance(class_id, str) or not class_id.strip():
            raise ValueError("VerbNet frame without grammatical class")
        matches[lemma.casefold()].add(class_id)
        valid_frames += 1
    return {
        "top_level_type": type(root).__name__,
        "top_level_keys": list(root)[:12],
        "frame_count": valid_frames,
        "lemma_count": len(matches),
        "lemmas": {lemma: sorted(classes) for lemma, classes in matches.items()},
    }


def load_wordnet(base: Path) -> object:
    url = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet.zip"
    data = download(url, base / "wordnet.zip", WORDNET_SHA256)
    import nltk
    root = base / "nltk_data"
    target = root / "corpora"
    target.mkdir(parents=True, exist_ok=True)
    zpath = target / "wordnet.zip"
    if not zpath.exists():
        zpath.write_bytes(data)
    if str(root) not in nltk.data.path:
        nltk.data.path.insert(0,str(root))
    from nltk.corpus import wordnet as wn
    return wn


def export_inventory(base: Path, packaged_verbnet: Path) -> dict:
    from .core import induce_evidence
    prefix = f"https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/{UD_COMMIT}/"
    conllu = download(prefix + "en_ewt-ud-train.conllu", base / "ud-ewt-train.conllu").decode("utf-8")
    ud = induce_evidence(conllu)
    erg = load_erg(base)
    frame = load_framenet(base)
    vn = load_verbnet(packaged_verbnet)
    wn = load_wordnet(base)
    return {"sources": SOURCES, "ud": ud, "erg": erg, "framenet": frame,
            "verbnet": vn, "wordnet_available": bool(wn.synsets("word"))}
