"""Reference-link detectors (REF-01 … REF-25).

Each detector is pure: it walks a parse tree / mention list and emits
:class:`~seman_parser.reference.ReferenceLink` records. Nothing here
knows what a dog or a fall is — only grammatical form.

Families and labels follow ``plans/coreference-guide.md``.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .chart import ChartItem
from .discourse import Mention
from .features import Atom
from .reference import ReferenceKind, ReferenceLink, ReferenceReport

# Closed-class reflexive forms (grammatical, not world knowledge).
_REFLEXIVES = frozenset(
    {
        "myself",
        "yourself",
        "himself",
        "herself",
        "itself",
        "ourselves",
        "yourselves",
        "themselves",
    }
)
# Expletive-looking forms: NO_LINK unless a real referent is forced.
_EXPLETIVE_SURFACES = frozenset({"it", "there"})
_PERSONAL_PRONOUNS = frozenset(
    {
        "i",
        "me",
        "my",
        "mine",
        "we",
        "us",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "it",
        "its",
        "they",
        "them",
        "their",
        "theirs",
    }
)
_REFLEXIVE_FEATURE = "reflexive"
_EXPLETIVE_FEATURE = "expletive"
_ANAPHOR_FEATURE = "anaphor"


def _feat(item: ChartItem | Mention, name: str) -> str | None:
    fs = item.features
    value = fs.get(name) if hasattr(fs, "get") else None
    if isinstance(value, Atom):
        return value.name
    return None


def _lemma(m: Mention) -> str:
    return (m.head_lemma or m.surface).strip().lower()


def _is_reflexive(m: Mention) -> bool:
    return _feat(m, _REFLEXIVE_FEATURE) in {"true", "yes", "1"} or m.surface.strip().lower() in _REFLEXIVES


def _is_expletive(m: Mention) -> bool:
    return _feat(m, _EXPLETIVE_FEATURE) in {"true", "yes", "1"} or (
        m.surface.strip().lower() in _EXPLETIVE_SURFACES and _feat(m, _EXPLETIVE_FEATURE) is not None
    )


def _is_pronoun(m: Mention) -> bool:
    return m.kind in {"pronoun", "demonstrative"} or m.surface.strip().lower() in _PERSONAL_PRONOUNS


def _rule(family: str, name: str) -> str:
    return f"{family}:{name}"


def _surface(item: ChartItem) -> str:
    if not item.children:
        detail = item.provenance.detail if item.provenance else {}
        return str(detail.get("surface", ""))
    parts = [_surface(child) for child in item.children]
    return " ".join(p for p in parts if p)


# -- tree helpers -------------------------------------------------------


def _walk(item: ChartItem) -> Iterable[ChartItem]:
    yield item
    for child in item.children:
        yield from _walk(child)


def _find_category(item: ChartItem, category: str) -> list[ChartItem]:
    return [n for n in _walk(item) if n.category == category]


# -- REF-01 reflexives --------------------------------------------------


def detect_reflexives(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-01: local reflexive ↔ clausemate antecedent (SAME_REF).

    Conservatism (guide §1): only emit when the parse exposes a unique
    clausemate NP that can host the binding. Otherwise MAYBE_REF.
    """
    out: list[ReferenceLink] = []
    clausemates = [
        m
        for m in mentions
        if m.sentence_index == sentence_index
        and not _is_reflexive(m)
        and not _is_pronoun(m)
        and m.kind in {"proper", "definite", "indefinite"}
    ]
    for m in mentions:
        if m.sentence_index != sentence_index or not _is_reflexive(m):
            continue
        if len(clausemates) == 1:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=clausemates[0].mention_id,
                    kind=ReferenceKind.SAME_REF,
                    rule_id=_rule("REF-01", "local-unique"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "antecedent": clausemates[0].surface},
                )
            )
        else:
            # Guide: un seul candidat grammatical ne signifie pas identité certaine.
            for cand in clausemates[:3]:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=cand.mention_id,
                        kind=ReferenceKind.MAYBE_REF,
                        rule_id=_rule("REF-01", "local-ambiguous"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface, "antecedent": cand.surface},
                    )
                )
            if not clausemates:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=None,
                        kind=ReferenceKind.NO_LINK,
                        rule_id=_rule("REF-01", "no-local-antecedent"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface},
                    )
                )
    return out


# -- REF-02 / REF-03 relatives ------------------------------------------


def detect_relatives(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-02/03: relative head ↔ relative operator / gap (SAME_REF)."""
    out: list[ReferenceLink] = []
    # np_relative_subj = NP WH-SUBJ ; np_relative_obj = NP WH-OBJ
    for node in _walk(tree):
        if node.category != "NP" or len(node.children) < 2:
            continue
        # look for WH-*/VP-GAP children under this NP
        cats = [c.category for c in node.children]
        head = next((c for c in node.children if c.category in {"N", "PROPER-NOUN", "NP"}), None)
        op = next((c for c in node.children if c.category.startswith("WH-")), None)
        gap = next((c for c in node.children if c.category in {"VP-GAP", "CLAUSE"}), None)
        if head is None:
            continue
        # REF-02: explicit relative operator
        if op is not None:
            out.append(
                ReferenceLink(
                    source=f"{parse_id or sentence_index}:{op.category}:{op.start}-{op.end}",
                    target=f"{sentence_index}:{head.category}:{head.start}-{head.end}",
                    kind=ReferenceKind.SAME_REF,
                    rule_id=_rule("REF-02", "explicit-operator"),
                    parse_id=parse_id,
                    evidence={
                        "head": head.provenance.detail.get("surface", ""),
                        "operator": op.category,
                        "cats": cats,
                    },
                )
            )
        # REF-03: zero relative / reduced relative (gap only)
        elif gap is not None and any(c.category in {"V", "VP-GAP", "VP"} for c in node.children):
            out.append(
                ReferenceLink(
                    source=f"{sentence_index}:GAP:{gap.start}-{gap.end}",
                    target=f"{sentence_index}:{head.category}:{head.start}-{head.end}",
                    kind=ReferenceKind.SAME_REF,
                    rule_id=_rule("REF-03", "zero-or-reduced"),
                    parse_id=parse_id,
                    evidence={"head": head.provenance.detail.get("surface", ""), "cats": cats},
                )
            )
    return out


# -- REF-04 shared arguments --------------------------------------------


def detect_shared_arguments(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-04: coordination shares an argument (SHARED_ARGUMENT)."""
    out: list[ReferenceLink] = []
    for node in _walk(tree):
        if node.category not in {"VP", "CLAUSE", "ADJP", "NP"}:
            continue
        kids = node.children
        # VP COORD VP  /  CLAUSE COORD CLAUSE  /  V COORD V …
        for i in range(len(kids) - 2):
            left, coord, right = kids[i], kids[i + 1], kids[i + 2]
            if coord.category != "COORD":
                continue
            if left.category != right.category:
                continue
            if node.category == "VP":
                # shared subject is outside this VP — link the two predicates
                out.append(
                    ReferenceLink(
                        source=f"{sentence_index}:VP:{left.start}-{left.end}",
                        target=f"{sentence_index}:VP:{right.start}-{right.end}",
                        kind=ReferenceKind.SHARED_ARGUMENT,
                        rule_id=_rule("REF-04", "vp-coord"),
                        parse_id=parse_id,
                        evidence={"shared": "subject", "rule": node.rule_id},
                    )
                )
            elif node.category == "CLAUSE":
                # clause coordination: only share if one side is a gapped VP
                left_has_subj = any(c.category == "NP" for c in left.children)
                right_has_subj = any(c.category == "NP" for c in right.children)
                if left_has_subj != right_has_subj:
                    out.append(
                        ReferenceLink(
                            source=f"{sentence_index}:CLAUSE:{right.start}-{right.end}"
                            if left_has_subj
                            else f"{sentence_index}:CLAUSE:{left.start}-{left.end}",
                            target=f"{sentence_index}:CLAUSE:{left.start}-{left.end}"
                            if left_has_subj
                            else f"{sentence_index}:CLAUSE:{right.start}-{right.end}",
                            kind=ReferenceKind.SHARED_ARGUMENT,
                            rule_id=_rule("REF-04", "clause-gapping"),
                            parse_id=parse_id,
                            evidence={"shared": "subject"},
                        )
                    )
    return out


# -- REF-05 local non-identity ------------------------------------------


def detect_non_identity(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-05: binding theory — object pronoun ≠ local subject (DIFFERENT_REF)."""
    out: list[ReferenceLink] = []
    clause = next((n for n in _walk(tree) if n.category == "CLAUSE"), None)
    if clause is None:
        return out
    subject = next(
        (m for m in mentions if m.sentence_index == sentence_index and m.kind in {"proper", "definite"}),
        None,
    )
    objects = [
        m
        for m in mentions
        if m.sentence_index == sentence_index
        and _is_pronoun(m)
        and not _is_reflexive(m)
        and m.surface.strip().lower() in {"him", "her", "them", "me", "us"}
    ]
    if subject is None:
        return out
    for obj in objects:
        if obj.mention_id == subject.mention_id:
            continue
        out.append(
            ReferenceLink(
                source=obj.mention_id,
                target=subject.mention_id,
                kind=ReferenceKind.DIFFERENT_REF,
                rule_id=_rule("REF-05", "object-vs-subject"),
                parse_id=parse_id,
                evidence={"subject": subject.surface, "object": obj.surface},
            )
        )
    return out


# -- REF-06 personal / possessive pronouns ------------------------------


def detect_personal_pronouns(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
) -> list[ReferenceLink]:
    """REF-06: personal/possessive pronouns are MAYBE_REF (never SAME_REF)."""
    out: list[ReferenceLink] = []
    pool = list(antecedents) or [
        m for m in mentions if m.sentence_index < sentence_index and not _is_pronoun(m)
    ]
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        if not _is_pronoun(m) or _is_reflexive(m) or _is_expletive(m):
            continue
        if m.surface.strip().lower() not in _PERSONAL_PRONOUNS:
            continue
        # Agreement filter only — never invents identity.
        candidates = [
            a
            for a in pool
            if _number_compatible(m, a) and _person_compatible(m, a)
        ]
        if not candidates:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-06", "no-candidate"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        for cand in candidates[:3]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=cand.mention_id,
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-06", "personal"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "antecedent": cand.surface},
                )
            )
    return out


def _number_compatible(a: Mention, b: Mention) -> bool:
    na, nb = a.number, b.number
    if na is None or nb is None:
        return True
    return na == nb


def _person_compatible(a: Mention, b: Mention) -> bool:
    pa, pb = a.person, b.person
    if pa is None or pb is None:
        return True
    return pa == pb


# -- REF-07 / REF-08 lexical repetition ---------------------------------


def _head_key(m: Mention, *, normalize: bool) -> str:
    """Nominal head form (guide §4: tête nominale, pas tout le NP)."""
    if normalize:
        return _lemma(m)
    # prefer explicit head lemma's surface form when available
    head = (m.head_lemma or "").strip().lower()
    if head:
        return head
    toks = m.surface.strip().lower().split()
    return toks[-1] if toks else ""


def detect_lexical_repetition(
    mentions: Sequence[Mention],
    *,
    parse_id: str = "",
    normalize: bool = False,
) -> list[ReferenceLink]:
    """REF-07 exact head repetition, REF-08 lemma-normalized (MAYBE_REF)."""
    family = "REF-08" if normalize else "REF-07"
    out: list[ReferenceLink] = []
    seen: list[Mention] = []
    for m in mentions:
        if _is_pronoun(m) or _is_reflexive(m):
            continue
        key = _head_key(m, normalize=normalize)
        if not key:
            continue
        for prev in seen:
            pkey = _head_key(prev, normalize=normalize)
            if pkey == key and prev.mention_id != m.mention_id:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=prev.mention_id,
                        kind=ReferenceKind.MAYBE_REF,
                        rule_id=_rule(family, "repeated-head"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface, "previous": prev.surface},
                    )
                )
        seen.append(m)
    return out


# -- REF-09 / REF-10 external & expletives ------------------------------


def detect_unresolved(
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    has_candidates: dict[str, bool] | None = None,
) -> list[ReferenceLink]:
    """REF-09 external referents, REF-10 expletives → NO_LINK."""
    out: list[ReferenceLink] = []
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        if _is_expletive(m):
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-10", "expletive"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        if _is_pronoun(m) and (has_candidates or {}).get(m.mention_id) is False:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-09", "external"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
    return out


# -- REF-11 appositions -------------------------------------------------


def detect_appositions(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    text: str = "",
) -> list[ReferenceLink]:
    """REF-11: identifying apposition → ASSERTED_IDENTITY.

    Guide: ``John, my brother, arrived.`` / ``A scientist, Dr. Smith, arrived.``
    The text *asserts* identity; that is not the same as grammar forcing it.

    The chart may analyse the pair as ``clause_front_np`` (NP COMMA CLAUSE)
    rather than ``np_appos_comma``. We therefore also inspect the mention
    stream: two nominal mentions separated only by a comma.
    """
    out: list[ReferenceLink] = []
    for node in _walk(tree):
        kids = node.children
        for i in range(len(kids) - 2):
            left, comma, right = kids[i], kids[i + 1], kids[i + 2]
            if comma.category != "COMMA":
                continue
            if left.category != "NP" or right.category != "NP":
                continue
            if any(c.category == "COORD" for c in kids):
                continue
            out.append(
                ReferenceLink(
                    source=f"{sentence_index}:NP:{right.start}-{right.end}",
                    target=f"{sentence_index}:NP:{left.start}-{left.end}",
                    kind=ReferenceKind.ASSERTED_IDENTITY,
                    rule_id=_rule("REF-11", "comma-apposition"),
                    parse_id=parse_id,
                    evidence={"left": _surface(left), "right": _surface(right)},
                )
            )

    # Mention-level: consecutive nominals separated by a comma only
    # (typical apposition). Never fuse subject and object of a verb.
    nominals = [
        m
        for m in mentions
        if m.sentence_index == sentence_index
        and m.kind in {"proper", "definite", "indefinite"}
        and not _is_pronoun(m)
    ]
    nominals = sorted(nominals, key=lambda m: m.span[0])
    for left, right in zip(nominals, nominals[1:]):
        if right.span[0] < left.span[1]:
            continue
        gap = text[left.span[1] : right.span[0]] if text else ""
        if "," not in gap:
            continue
        # only proper+nominal or nominal+proper apposition patterns
        if left.kind == right.kind == "proper":
            pair_ok = True
        elif left.kind == "proper" and right.kind in {"definite", "indefinite"}:
            pair_ok = True
        elif left.kind in {"indefinite", "definite"} and right.kind == "proper":
            pair_ok = True
        else:
            pair_ok = False
        if not pair_ok:
            continue
        out.append(
            ReferenceLink(
                source=right.mention_id,
                target=left.mention_id,
                kind=ReferenceKind.ASSERTED_IDENTITY,
                rule_id=_rule("REF-11", "mention-adjacent"),
                parse_id=parse_id,
                evidence={"left": left.surface, "right": right.surface, "gap": gap},
            )
        )
    return out


# -- REF-12 intensifying reflexives -------------------------------------


def detect_intensifiers(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-12: ``John himself answered`` — emphatic apposition.

    Guide: intensifying reflexives are identity with the host NP, under
    the analysis. Emits ASSERTED_IDENTITY (emphasis, not a new referent).
    """
    out: list[ReferenceLink] = []
    for node in _walk(tree):
        kids = node.children
        for i in range(len(kids) - 1):
            left, right = kids[i], kids[i + 1]
            left_surf = _surface(left).strip().lower()
            right_surf = _surface(right).strip().lower()
            # NP + reflexive intensifier (or reverse)
            pair = None
            if right_surf in _REFLEXIVES and left.category in {"NP", "PROPER-NOUN", "N"}:
                pair = (left, right)
            elif left_surf in _REFLEXIVES and right.category in {"NP", "PROPER-NOUN", "N"}:
                pair = (right, left)
            if pair is None:
                continue
            host, intensifier = pair
            out.append(
                ReferenceLink(
                    source=f"{sentence_index}:INT:{intensifier.start}-{intensifier.end}",
                    target=f"{sentence_index}:NP:{host.start}-{host.end}",
                    kind=ReferenceKind.ASSERTED_IDENTITY,
                    rule_id=_rule("REF-12", "intensifier"),
                    parse_id=parse_id,
                    evidence={"host": _surface(host), "intensifier": _surface(intensifier)},
                )
            )
    return out


# -- REF-13 demonstratives ----------------------------------------------


def detect_demonstratives(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
) -> list[ReferenceLink]:
    """REF-13: this/that/these/those as anaphors → MAYBE_REF.

    Never SAME_REF: the guide keeps an external referent possible even
    with a single grammatical candidate.
    """
    out: list[ReferenceLink] = []
    pool = list(antecedents) or [
        m for m in mentions if m.sentence_index < sentence_index and not _is_pronoun(m)
    ]
    demonstratives = {"this", "that", "these", "those"}
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = m.surface.strip().lower()
        if surf not in demonstratives and m.kind != "demonstrative":
            continue
        if _is_reflexive(m):
            continue
        for cand in pool[:3]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=cand.mention_id,
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-13", "demonstrative"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "antecedent": cand.surface},
                )
            )
        if not pool:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-13", "no-candidate"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
    return out


# -- REF-14 ordinals / former / latter ----------------------------------


def detect_ordinals(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-14: the former / the latter / the first → MAYBE_REF.

    Only fires when the same sentence (or immediately preceding) has a
    coordinated pair — guide: "si la paire est non ambiguë".
    """
    out: list[ReferenceLink] = []
    markers = {
        "the former": "first",
        "former": "first",
        "the latter": "second",
        "latter": "second",
        "the first": "first",
        "the second": "second",
    }
    # Find coordinated NP pairs in the tree.
    pairs: list[tuple[ChartItem, ChartItem]] = []
    for node in _walk(tree):
        kids = node.children
        for i in range(len(kids) - 2):
            left, coord, right = kids[i], kids[i + 1], kids[i + 2]
            if coord.category == "COORD" and left.category == right.category:
                pairs.append((left, right))

    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = " ".join(m.surface.strip().lower().split())
        slot = markers.get(surf)
        if slot is None:
            continue
        if not pairs:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-14", "no-pair"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        left, right = pairs[0]
        target_surface = _surface(left) if slot == "first" else _surface(right)
        # Map to a mention if one matches the chosen conjunct.
        target = next(
            (x for x in mentions if x.surface.strip().lower() == target_surface.strip().lower()),
            None,
        )
        out.append(
            ReferenceLink(
                source=m.mention_id,
                target=target.mention_id if target else f"{sentence_index}:COORD:{slot}",
                kind=ReferenceKind.MAYBE_REF,
                rule_id=_rule("REF-14", "ordinal"),
                parse_id=parse_id,
                evidence={"surface": m.surface, "slot": slot, "antecedent": target_surface},
            )
        )
    return out


# -- REF-15 collective / plural groups ----------------------------------


def detect_collectives(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-15: both / all three / the two → MAYBE_REF over the group.

    Guide: "Référence au groupe ou quantification sur ses membres, selon
    la construction" — we emit MAYBE_REF on the coordinated conjuncts.
    """
    out: list[ReferenceLink] = []
    markers = {"both", "all three", "the two", "all two", "the three", "all"}
    pairs: list[tuple[ChartItem, ChartItem]] = []
    for node in _walk(tree):
        kids = node.children
        for i in range(len(kids) - 2):
            left, coord, right = kids[i], kids[i + 1], kids[i + 2]
            if coord.category == "COORD" and left.category == right.category:
                pairs.append((left, right))

    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = " ".join(m.surface.strip().lower().split())
        if surf not in markers:
            continue
        if not pairs:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-15", "no-group"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        left, right = pairs[0]
        for part, slot in ((left, "left"), (right, "right")):
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=f"{sentence_index}:COORD:{part.start}-{part.end}",
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-15", "collective"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "slot": slot, "member": _surface(part)},
                )
            )
    return out


# -- REF-16 explicit identity markers -----------------------------------


def detect_identity_markers(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-16: aka / named / same person as → ASSERTED_IDENTITY.

    Guide §5: a tiny closed set of conventional English operators. This
    is not world knowledge — it is recognizing a construction.
    """
    out: list[ReferenceLink] = []
    # surfaces that introduce an asserted identity
    patterns = (
        ("also known as", "aka"),
        ("aka", "aka"),
        ("named", "named"),
        ("called", "called"),
        ("the same person as", "same-as"),
        ("the same as", "same-as"),
    )
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = " ".join(m.surface.strip().lower().split())
        for needle, label in patterns:
            if needle not in surf:
                continue
            # Link the mention to the nearest other NP mention in the same
            # sentence — the asserted pair.
            others = [
                o
                for o in mentions
                if o.sentence_index == sentence_index and o.mention_id != m.mention_id
            ]
            if not others:
                continue
            target = others[0]
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=target.mention_id,
                    kind=ReferenceKind.ASSERTED_IDENTITY,
                    rule_id=_rule("REF-16", label),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "marker": needle, "target": target.surface},
                )
            )
    return out


# -- REF-17 explicit difference markers ---------------------------------


def detect_difference_markers(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-17: another / a different / someone else → DIFFERENT_REF."""
    out: list[ReferenceLink] = []
    markers = {
        "another": "another",
        "a different": "different",
        "different": "different",
        "someone else": "else",
        "somebody else": "else",
        "something else": "else",
        "anyone else": "else",
        "else": "else",
        "not the same": "not-same",
    }
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = " ".join(m.surface.strip().lower().split())
        lemma = _lemma(m)
        label = None
        for needle, lab in markers.items():
            if needle in surf or needle == lemma:
                label = lab
                break
        if label is None:
            continue
        others = [
            o
            for o in mentions
            if o.sentence_index <= sentence_index
            and o.mention_id != m.mention_id
            and not _is_pronoun(o)
            and o.kind != "event"
        ]
        if not others:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.DIFFERENT_REF,
                    rule_id=_rule("REF-17", label),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        for other in others[:2]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=other.mention_id,
                    kind=ReferenceKind.DIFFERENT_REF,
                    rule_id=_rule("REF-17", label),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "distinct-from": other.surface},
                )
            )
    return out


# -- REF-18 first / second person ---------------------------------------


def detect_speaker_reference(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    speaker_id: str | None = None,
    addressee_id: str | None = None,
) -> list[ReferenceLink]:
    """REF-18: I/we/you — MAYBE_REF only with a communication anchor.

    Guide: without a reliable speaker identifier, grammar alone cannot
    link two ``I`` from different sources. With ``speaker_id``, SAME_REF
    among first-person forms; otherwise NO_LINK / external.
    """
    out: list[ReferenceLink] = []
    first = {"i", "me", "my", "mine", "we", "us", "our", "ours", "myself", "ourselves"}
    second = {"you", "your", "yours", "yourself", "yourselves"}
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = m.surface.strip().lower()
        if surf in first:
            if speaker_id:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=speaker_id,
                        kind=ReferenceKind.SAME_REF,
                        rule_id=_rule("REF-18", "speaker-anchored"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface, "anchor": speaker_id},
                    )
                )
            else:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=None,
                        kind=ReferenceKind.NO_LINK,
                        rule_id=_rule("REF-18", "unanchored-1st"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface},
                    )
                )
        elif surf in second:
            if addressee_id:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=addressee_id,
                        kind=ReferenceKind.SAME_REF,
                        rule_id=_rule("REF-18", "addressee-anchored"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface, "anchor": addressee_id},
                    )
                )
            else:
                out.append(
                    ReferenceLink(
                        source=m.mention_id,
                        target=None,
                        kind=ReferenceKind.NO_LINK,
                        rule_id=_rule("REF-18", "unanchored-2nd"),
                        parse_id=parse_id,
                        evidence={"surface": m.surface},
                    )
                )
    return out


# -- REF-19 bound variables ---------------------------------------------


def detect_bound_variables(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-19: quantifier binding → BOUND_VARIABLE (not individual coref).

    Guide: ``Every student washed themselves`` links grammatically without
    inventing a particular student. Determiners every/each/all/no/any
    license a bound-variable reading of same-sentence pronouns.
    """
    out: list[ReferenceLink] = []
    quantifiers = {"every", "each", "all", "no", "any", "anyone", "everyone", "everybody"}
    # Find quantified NPs and pronouns in the same sentence.
    quantified: list[Mention] = []
    pronouns: list[Mention] = []
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = m.surface.strip().lower()
        first_tok = surf.split()[0] if surf.split() else ""
        if first_tok in quantifiers or any(t in quantifiers for t in surf.split()[:2]):
            quantified.append(m)
        if _is_pronoun(m) or _is_reflexive(m):
            pronouns.append(m)

    for q in quantified:
        for p in pronouns:
            if p.mention_id == q.mention_id:
                continue
            if not (_number_compatible(p, q) or _is_reflexive(p)):
                continue
            out.append(
                ReferenceLink(
                    source=p.mention_id,
                    target=q.mention_id,
                    kind=ReferenceKind.BOUND_VARIABLE,
                    rule_id=_rule("REF-19", "quantifier-binding"),
                    parse_id=parse_id,
                    evidence={"quantifier": q.surface, "pronoun": p.surface},
                )
            )
    return out


# -- REF-20 nominal ellipsis (one/ones) ---------------------------------


def detect_nominal_ellipsis(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-20: ``a red one`` → TYPE_ANAPHORA, never individual identity.

    Guide §4/§7: *one* reprend souvent un type de chose, pas un référent
    individuel. Kind is TYPE_ANAPHORA even when a unique antecedent exists.
    """
    out: list[ReferenceLink] = []
    ones = {"one", "ones"}
    candidates = [
        m
        for m in mentions
        if m.sentence_index == sentence_index
        and m.surface.strip().lower().split()[-1:] and m.surface.strip().lower().split()[-1] not in ones
        and not _is_pronoun(m)
        and m.kind != "event"
    ]
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        toks = m.surface.strip().lower().split()
        if not toks or toks[-1] not in ones:
            continue
        if not candidates:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.TYPE_ANAPHORA,
                    rule_id=_rule("REF-20", "no-type"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        for cand in candidates[:2]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=cand.mention_id,
                    kind=ReferenceKind.TYPE_ANAPHORA,
                    rule_id=_rule("REF-20", "one-type"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "type_source": cand.surface},
                )
            )
    return out


# -- REF-21 verbal / propositional ellipsis -----------------------------


def detect_verbal_ellipsis(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
) -> list[ReferenceLink]:
    """REF-21: VP/so/do ellipsis → MAYBE_REF on the antecedent event.

    Structures: ``clause_aux_ellipsis`` / ``clause_modal_ellipsis`` /
    ``clause_ellipsis_*`` — AUX without a full VP recovers material from
    the left conjunct or the previous sentence. Never SAME_REF: the
    recovered material is a situation, not an individual.
    """
    out: list[ReferenceLink] = []
    elliptical_rules = {
        "clause_aux_ellipsis",
        "clause_modal_ellipsis",
        "clause_cop_ellipsis",
        "clause_ellipsis_too",
        "clause_ellipsis_degree",
        "clause_pred_ellipsis",
    }
    for node in _walk(tree):
        if node.rule_id not in elliptical_rules:
            continue
        # The elliptical clause shares material with a sibling/left context.
        surface = _surface(node)
        out.append(
            ReferenceLink(
                source=f"{sentence_index}:ELL:{node.start}-{node.end}",
                target=None,
                kind=ReferenceKind.MAYBE_REF,
                rule_id=_rule("REF-21", "vp-ellipsis"),
                parse_id=parse_id,
                evidence={"surface": surface, "rule": node.rule_id},
            )
        )
    # Token-level ``so`` / bare ``do`` as VP pro-forms.
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        surf = m.surface.strip().lower()
        if surf not in {"so", "do", "does", "did", "not"}:
            continue
        # Prefer an event antecedent in prior material.
        prior_events = [
            a
            for a in antecedents
            if a.kind == "event" or (a.head_lemma and a.head_lemma == m.head_lemma)
        ]
        if prior_events:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=prior_events[0].mention_id,
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-21", "pro-form"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "antecedent": prior_events[0].surface},
                )
            )
    return out


# -- REF-22 control and raising -----------------------------------------


def detect_control_raising(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-22: subject/object control and raising → SHARED_ARGUMENT.

    Guide §2: ``John tried to leave`` shares the participant; ``John seems
    to be sleeping`` shares an argument under raising. Only fire on the
    grammar rules that already encode the structure
    (``vp_to_inf`` / ``vp_obj_control`` / ``vp_obj_control_bare``).
    """
    out: list[ReferenceLink] = []
    control_rules = {"vp_to_inf", "vp_obj_control", "vp_obj_control_bare", "vp_cop_np_inf"}
    for node in _walk(tree):
        if node.rule_id not in control_rules:
            continue
        # Find the matrix subject/subject-like NP and the embedded VP.
        nps = [c for c in _walk(node) if c.category in {"NP", "PROPER-NOUN", "PRONOUN"}]
        vps = [c for c in _walk(node) if c.category in {"VP", "VP-NP"}]
        if not nps or not vps:
            continue
        subject = nps[0]
        embedded = vps[-1]
        out.append(
            ReferenceLink(
                source=f"{sentence_index}:VP:{embedded.start}-{embedded.end}",
                target=f"{sentence_index}:NP:{subject.start}-{subject.end}",
                kind=ReferenceKind.SHARED_ARGUMENT,
                rule_id=_rule("REF-22", node.rule_id),
                parse_id=parse_id,
                evidence={"subject": _surface(subject), "embedded": _surface(embedded)},
            )
        )
    return out


# -- REF-23 event / proposition anaphora --------------------------------


def detect_event_anaphora(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
) -> list[ReferenceLink]:
    """REF-23: this/that over a clause → MAYBE_REF on the event.

    Guide P2: demonstrative pronouns can pick out a whole situation.
    Kind stays MAYBE_REF (not SAME_REF): several events may compete.
    """
    out: list[ReferenceLink] = []
    demonstrative_prons = {"this", "that", "these", "those", "it"}
    pool = list(antecedents) or list(mentions)
    prior_events = [a for a in pool if a.kind == "event" or a.semantic_type == "EVENT"]
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        if m.surface.strip().lower() not in demonstrative_prons:
            continue
        if not prior_events:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=None,
                    kind=ReferenceKind.NO_LINK,
                    rule_id=_rule("REF-23", "no-event"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface},
                )
            )
            continue
        for ev in prior_events[:2]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=ev.mention_id,
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-23", "event-anaphor"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "event": ev.surface},
                )
            )
    return out


# -- REF-24 cataphora ---------------------------------------------------


def detect_cataphora(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    later: Sequence[Mention] = (),
) -> list[ReferenceLink]:
    """REF-24: forward reference → MAYBE_REF toward a later mention.

    Guide P2: the anaphor precedes its antecedent. We only look at
    same-sentence later mentions (across-sentence cataphora is rarer and
    needs a discourse window the caller supplies via ``later``).
    """
    out: list[ReferenceLink] = []
    ordered = sorted(
        [m for m in mentions if m.sentence_index == sentence_index],
        key=lambda m: m.span[0],
    )
    for i, m in enumerate(ordered):
        if not (_is_pronoun(m) or m.kind == "demonstrative"):
            continue
        following = [x for x in ordered[i + 1 :] if not _is_pronoun(x) and x.kind != "event"]
        following = list(following) + [
            x for x in later if x.sentence_index > sentence_index
        ]
        for cand in following[:2]:
            out.append(
                ReferenceLink(
                    source=m.mention_id,
                    target=cand.mention_id,
                    kind=ReferenceKind.MAYBE_REF,
                    rule_id=_rule("REF-24", "forward"),
                    parse_id=parse_id,
                    evidence={"surface": m.surface, "later": cand.surface},
                )
            )
    return out


# -- REF-25 associative anaphora (OUT) ----------------------------------


def detect_associative(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
) -> list[ReferenceLink]:
    """REF-25: bridging / associative anaphora — OUT of the parser.

    Guide: "Hors parseur, sauf marquage non résolu." We never invent a
    link from world knowledge. Definite NPs with no textual antecedent
    are simply left unresolved (NO_LINK) so a later layer can decide.
    """
    out: list[ReferenceLink] = []
    for m in mentions:
        if m.sentence_index != sentence_index:
            continue
        if m.kind != "definite":
            continue
        if _is_pronoun(m) or _is_reflexive(m):
            continue
        # Definite with no textual antecedent candidate in earlier sentences
        # is the *possible* bridging site. We record NO_LINK, not a guess.
        out.append(
            ReferenceLink(
                source=m.mention_id,
                target=None,
                kind=ReferenceKind.NO_LINK,
                rule_id=_rule("REF-25", "associative-unresolved"),
                parse_id=parse_id,
                evidence={"surface": m.surface},
            )
        )
    return out


# -- driver -------------------------------------------------------------


def detect_p0(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
) -> ReferenceReport:
    """Run the P0 family set over one sentence's analysis."""
    report = ReferenceReport(parse_id=parse_id)
    for link in detect_reflexives(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_relatives(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_shared_arguments(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_non_identity(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_personal_pronouns(
        tree,
        mentions,
        sentence_index=sentence_index,
        parse_id=parse_id,
        antecedents=antecedents,
    ):
        report.add(link)
    for link in detect_lexical_repetition(mentions, parse_id=parse_id, normalize=False):
        report.add(link)
    for link in detect_lexical_repetition(mentions, parse_id=parse_id, normalize=True):
        report.add(link)
    return report


def detect_p1(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
    speaker_id: str | None = None,
    addressee_id: str | None = None,
    text: str = "",
) -> ReferenceReport:
    """Run the P1 family set (REF-11 … REF-19)."""
    report = ReferenceReport(parse_id=parse_id)
    for link in detect_appositions(
        tree, mentions, sentence_index=sentence_index, parse_id=parse_id, text=text
    ):
        report.add(link)
    for link in detect_intensifiers(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_demonstratives(
        tree, mentions, sentence_index=sentence_index, parse_id=parse_id, antecedents=antecedents
    ):
        report.add(link)
    for link in detect_ordinals(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_collectives(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_identity_markers(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_difference_markers(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_speaker_reference(
        tree,
        mentions,
        sentence_index=sentence_index,
        parse_id=parse_id,
        speaker_id=speaker_id,
        addressee_id=addressee_id,
    ):
        report.add(link)
    for link in detect_bound_variables(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    return report


def detect_p2(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
    later: Sequence[Mention] = (),
) -> ReferenceReport:
    """Run the P2 family set (REF-20 … REF-25)."""
    report = ReferenceReport(parse_id=parse_id)
    for link in detect_nominal_ellipsis(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_verbal_ellipsis(
        tree, mentions, sentence_index=sentence_index, parse_id=parse_id, antecedents=antecedents
    ):
        report.add(link)
    for link in detect_control_raising(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    for link in detect_event_anaphora(
        tree, mentions, sentence_index=sentence_index, parse_id=parse_id, antecedents=antecedents
    ):
        report.add(link)
    for link in detect_cataphora(
        tree, mentions, sentence_index=sentence_index, parse_id=parse_id, later=later
    ):
        report.add(link)
    for link in detect_associative(tree, mentions, sentence_index=sentence_index, parse_id=parse_id):
        report.add(link)
    return report


def detect_all(
    tree: ChartItem,
    mentions: Sequence[Mention],
    *,
    sentence_index: int,
    parse_id: str = "",
    antecedents: Sequence[Mention] = (),
    speaker_id: str | None = None,
    addressee_id: str | None = None,
    later: Sequence[Mention] = (),
    text: str = "",
) -> ReferenceReport:
    """P0 + P1 + P2 families."""
    report = detect_p0(
        tree,
        mentions,
        sentence_index=sentence_index,
        parse_id=parse_id,
        antecedents=antecedents,
    )
    p1 = detect_p1(
        tree,
        mentions,
        sentence_index=sentence_index,
        parse_id=parse_id,
        antecedents=antecedents,
        speaker_id=speaker_id,
        addressee_id=addressee_id,
        text=text,
    )
    for link in p1.links:
        report.add(link)
    p2 = detect_p2(
        tree,
        mentions,
        sentence_index=sentence_index,
        parse_id=parse_id,
        antecedents=antecedents,
        later=later,
    )
    for link in p2.links:
        report.add(link)
    return report
