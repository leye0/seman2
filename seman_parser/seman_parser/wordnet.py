"""Pure-Python reader for the WordNet 3.0 database files.

No NLTK, no network. Reads the on-disk ``dict/`` files shipped with the
project (``.local/share/wordnet/WordNet-3.0/dict``).

WordNet is a lexical resource: it supplies lemmas, parts of speech,
morphological variants and lexicographer files. The engine never hardcodes
those lists — it imports them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

# WordNet POS letters used in the index/data files.
POS_NOUN = "n"
POS_VERB = "v"
POS_ADJ = "a"
POS_ADV = "r"
POS_SATELLITE = "s"  # adjective satellite (data.adj only)

_POS_SUFFIX = {
    POS_NOUN: "noun",
    POS_VERB: "verb",
    POS_ADJ: "adj",
    POS_ADV: "adv",
    POS_SATELLITE: "adj",
}


@dataclass(frozen=True, slots=True)
class WordNetWord:
    """One surface form inside a synset."""

    lemma: str  # underscores, e.g. "take_a_breath"
    lex_id: int


@dataclass(frozen=True, slots=True)
class WordNetPointer:
    symbol: str
    target_offset: int
    target_pos: str
    source_target: tuple[int, int]


@dataclass(frozen=True, slots=True)
class WordNetFrame:
    """Verb subcategorization frame number + which word it applies to."""

    frame_number: int
    word_number: int  # 1-based index in the synset word list


@dataclass(frozen=True, slots=True)
class WordNetSynset:
    offset: int
    pos: str
    lex_file: str  # e.g. "noun.animal"
    words: tuple[WordNetWord, ...]
    pointers: tuple[WordNetPointer, ...] = ()
    frames: tuple[WordNetFrame, ...] = ()
    gloss: str = ""

    @property
    def name(self) -> str:
        head = self.words[0].lemma if self.words else f"offset{self.offset}"
        return f"{head}-{self.pos}"


@dataclass(frozen=True, slots=True)
class WordNetEntry:
    """All synsets for one lemma + one POS."""

    lemma: str
    pos: str
    synset_offsets: tuple[int, ...]
    tag_count: int = 0


class WordNet:
    """Read-only view over a WordNet ``dict`` directory."""

    def __init__(self, dict_dir: str | Path) -> None:
        self.dict_dir = Path(dict_dir)
        if not self.dict_dir.is_dir():
            raise FileNotFoundError(f"WordNet dict directory not found: {self.dict_dir}")
        self._index: dict[tuple[str, str], WordNetEntry] = {}
        self._synsets: dict[tuple[int, str], WordNetSynset] = {}
        self._exceptions: dict[tuple[str, str], dict[str, str]] = {}
        self._lexnames: dict[int, str] = {}
        self._loaded_index = False
        self._loaded_data: set[str] = set()

    # -- index -----------------------------------------------------------

    def _index_path(self, pos: str) -> Path:
        return self.dict_dir / f"index.{_POS_SUFFIX[pos]}"

    def _data_path(self, pos: str) -> Path:
        return self.dict_dir / f"data.{_POS_SUFFIX[pos]}"

    def _exc_path(self, pos: str) -> Path:
        return self.dict_dir / f"{_POS_SUFFIX[pos]}.exc"

    def load_index(self) -> None:
        if self._loaded_index:
            return
        self._load_lexnames()
        for pos in (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV):
            path = self._index_path(pos)
            if not path.exists():
                continue
            for entry in _parse_index_file(path, pos):
                self._index[(entry.lemma, entry.pos)] = entry
        self._loaded_index = True

    def _load_lexnames(self) -> None:
        path = self.dict_dir / "lexnames"
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].isdigit():
                self._lexnames[int(parts[0])] = parts[1]

    def load_data(self, pos: str) -> None:
        self.load_index()
        if pos in self._loaded_data:
            return
        path = self._data_path(pos)
        if path.exists():
            for synset in _parse_data_file(path, pos, self._lexnames):
                self._synsets[(synset.offset, synset.pos)] = synset
        self._loaded_data.add(pos)

    def load_all(self) -> None:
        for pos in (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV):
            self.load_data(pos)

    # -- queries ---------------------------------------------------------

    def lookup(self, lemma: str, pos: str | None = None) -> Sequence[WordNetEntry]:
        self.load_index()
        key_lemma = lemma.lower().replace(" ", "_")
        if pos is not None:
            entry = self._index.get((key_lemma, pos))
            return (entry,) if entry else ()
        found = [
            self._index[(key_lemma, p)]
            for p in (POS_NOUN, POS_VERB, POS_ADJ, POS_ADV)
            if (key_lemma, p) in self._index
        ]
        return tuple(found)

    def synset(self, offset: int, pos: str) -> WordNetSynset | None:
        self.load_data(pos)
        return self._synsets.get((offset, pos))

    def synsets_for(self, lemma: str, pos: str | None = None) -> Sequence[WordNetSynset]:
        out: list[WordNetSynset] = []
        for entry in self.lookup(lemma, pos):
            self.load_data(entry.pos)
            for offset in entry.synset_offsets:
                synset = self._synsets.get((offset, entry.pos))
                if synset is not None:
                    out.append(synset)
        return out

    def exceptions(self, pos: str) -> Mapping[str, str]:
        """Irregular morphology map: surface -> lemma."""
        if pos in self._exceptions:
            return self._exceptions[pos]
        path = self._exc_path(pos)
        table: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    table[parts[0]] = parts[1]
        self._exceptions[pos] = table
        return table

    def morphological_forms(self, lemma: str, pos: str) -> Mapping[str, str]:
        """All surface forms WordNet knows: surface -> base lemma."""
        base = lemma.lower().replace(" ", "_")
        forms: dict[str, str] = {base.replace("_", " "): base.replace("_", " ")}
        for surface, target in self.exceptions(pos).items():
            if target == base or target.replace("_", " ") == base.replace("_", " "):
                forms[surface] = base.replace("_", " ")
        return forms

    def words(self, pos: str | None = None) -> Iterator[str]:
        self.load_index()
        for lemma, entry_pos in self._index:
            if pos is None or entry_pos == pos:
                yield lemma

    def __len__(self) -> int:
        self.load_index()
        return len(self._index)


def _parse_index_file(path: Path, pos: str) -> Iterable[WordNetEntry]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith(" "):
                continue  # license header
            parts = line.split()
            # lemma pos synset_cnt p_cnt [ptr...] sense_cnt tagsense_cnt offsets...
            if len(parts) < 7:
                continue
            lemma = parts[0]
            try:
                synset_cnt = int(parts[2])
                p_cnt = int(parts[3])
            except ValueError:
                continue
            cursor = 4 + p_cnt
            if cursor + 2 > len(parts):
                continue
            try:
                sense_cnt = int(parts[cursor])
                tag_count = int(parts[cursor + 1])
            except ValueError:
                continue
            offsets = tuple(
                int(x) for x in parts[cursor + 2 : cursor + 2 + synset_cnt] if x.isdigit()
            )
            yield WordNetEntry(
                lemma=lemma,
                pos=pos,
                synset_offsets=offsets,
                tag_count=tag_count,
            )


def _parse_data_file(path: Path, pos: str, lexnames: Mapping[int, str]) -> Iterable[WordNetSynset]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith(" "):
                continue
            synset = _parse_data_line(line, pos, lexnames)
            if synset is not None:
                yield synset


def _parse_data_line(line: str, pos: str, lexnames: Mapping[int, str]) -> WordNetSynset | None:
    # synset_offset lex_filenum ss_type w_cnt word lex_id [word lex_id...]
    #   p_cnt [ptr_symbol offset pos source_target...] [f_cnt [+ f_num w_num...]] | gloss
    if "|" in line:
        body, gloss = line.split("|", 1)
        gloss = gloss.strip()
    else:
        body, gloss = line, ""
    parts = body.split()
    if len(parts) < 6:
        return None
    try:
        offset = int(parts[0])
        lex_filenum = int(parts[1])
    except ValueError:
        return None
    ss_type = parts[2]
    try:
        w_cnt = int(parts[3], 16)  # word count is hexadecimal in WordNet
    except ValueError:
        return None
    cursor = 4
    words: list[WordNetWord] = []
    for _ in range(w_cnt):
        if cursor + 1 >= len(parts):
            break
        lemma = parts[cursor]
        try:
            lex_id = int(parts[cursor + 1])
        except ValueError:
            lex_id = 0
        words.append(WordNetWord(lemma=lemma, lex_id=lex_id))
        cursor += 2
    if cursor >= len(parts):
        return WordNetSynset(
            offset=offset,
            pos=ss_type,
            lex_file=lexnames.get(lex_filenum, f"lex{lex_filenum:02d}"),
            words=tuple(words),
            gloss=gloss,
        )
    try:
        p_cnt = int(parts[cursor])
    except ValueError:
        p_cnt = 0
    cursor += 1
    pointers: list[WordNetPointer] = []
    for _ in range(p_cnt):
        # symbol offset pos source_target (4 tokens)
        if cursor + 3 >= len(parts):
            break
        symbol = parts[cursor]
        try:
            target_offset = int(parts[cursor + 1])
        except ValueError:
            break
        target_pos = parts[cursor + 2]
        st = parts[cursor + 3]
        source = target = 0
        if len(st) == 8:
            try:
                source = int(st[:4])
                target = int(st[4:])
            except ValueError:
                source = target = 0
        pointers.append(
            WordNetPointer(
                symbol=symbol,
                target_offset=target_offset,
                target_pos=target_pos,
                source_target=(source, target),
            )
        )
        cursor += 4

    frames: list[WordNetFrame] = []
    if ss_type == POS_VERB and cursor < len(parts):
        try:
            f_cnt = int(parts[cursor])
        except ValueError:
            f_cnt = 0
        cursor += 1
        for _ in range(f_cnt):
            # "+" frame_num word_num
            if cursor + 2 >= len(parts) + 1 and cursor + 2 > len(parts):
                break
            if cursor + 2 <= len(parts) and parts[cursor] == "+":
                try:
                    frame_number = int(parts[cursor + 1])
                    word_number = int(parts[cursor + 2])
                except ValueError:
                    break
                frames.append(WordNetFrame(frame_number=frame_number, word_number=word_number))
                cursor += 3

    return WordNetSynset(
        offset=offset,
        pos=ss_type,
        lex_file=lexnames.get(lex_filenum, f"lex{lex_filenum:02d}"),
        words=tuple(words),
        pointers=tuple(pointers),
        frames=tuple(frames),
        gloss=gloss,
    )


def open_wordnet(dict_dir: str | Path) -> WordNet:
    return WordNet(dict_dir)


# Shared instance: the WordNet index costs ~3s to load. Every parser in the
# process reuses one read-only database.
_SHARED: dict[str, WordNet] = {}


def shared_wordnet(dict_dir: str | Path) -> WordNet:
    key = str(Path(dict_dir).resolve())
    instance = _SHARED.get(key)
    if instance is None:
        instance = WordNet(dict_dir)
        _SHARED[key] = instance
    return instance
