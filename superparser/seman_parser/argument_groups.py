"""Read-only evidence for argument slots exported by selected syntax.

The first witness is deliberately narrow. An accepted VP coordination is
not by itself proof of two independently finite predicates. This observer
does not change recognition, ranking, lexical alternatives, or syntax.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

FINITE_CARRIERS = frozenset({"AUX", "AUX-BE", "COPULA", "HAVE", "MODAL"})


def finite_carrier_surfaces(lexicon):
    """Read the closed inventory without promoting or looking up a sense."""
    return frozenset(
        surface.casefold()
        for entry in getattr(lexicon, "entries", ())
        if any(sense.category in FINITE_CARRIERS and _values(sense).get("vform") == "finite"
               for sense in entry.senses)
        for surface in entry.surfaces
    )


@dataclass(frozen=True, slots=True)
class ArgumentGroup:
    """An open syntactic slot of several owners in one declared domain."""

    slot: str
    owners: tuple[str, ...]
    constraints: tuple[tuple[str, str], ...]
    marker: str | None = None


def _nodes(item):
    yield item
    for child in item.children:
        yield from _nodes(child)


def _values(item):
    return item.features.as_dict()


def _agreement(item):
    values = _values(item)
    return {name: value for name in ("number", "person")
            if isinstance((value := values.get(name)), str) and not value.startswith("?")}


def _clause_boundary(category):
    return (category == "CLAUSE" or "CLAUSE" in category.split("-")
            or category in {"WH-OBJ", "WH-SUBJ", "QUESTION",
                            "OPEN-QUOTE", "CLOSE-QUOTE", "SEMICOLON", "SPEECH-STOP"})


def _finite_carrier(parent, head_child):
    """Recognize a separate, overt finite carrier along the owner's VP path."""
    values = _values(parent)
    if values.get("vform") != "finite":
        return None
    if values.get("modal") == "true":
        category, form = {"MODAL"}, "base"
    elif values.get("aspect") == "perfect":
        category, form = {"HAVE"}, "ed"
    elif values.get("aspect") == "progressive":
        category, form = {"AUX-BE", "COPULA"}, "ing"
    else:
        return None
    carriers = [child for child in parent.children if child.category in category
                and child.end <= head_child.start and child.lexical_candidate is not None
                and _values(child.lexical_candidate).get("vform") == "finite"]
    return (carriers[0], form) if len(carriers) == 1 else None


def _independent_finite_head(branch, anchor):
    values = _values(branch)
    if branch.category != "VP" or values.get("vform") != "finite":
        return None
    if any(_clause_boundary(node.category) or node.category in {"VP-GAP", "COMMA"}
           for node in _nodes(branch)):
        return None
    head = branch
    active = False
    carrier = None
    path_nonfinite = set()
    while head.children:
        if head.category not in {"VP", "VP-NP"}:
            return None
        if head.category == "VP-NP":
            if carrier is None or carrier[1] != "base":
                return None
            path_nonfinite.add(id(head))
        voice = _values(head).get("voice")
        if voice not in (None, "active"):
            return None
        active |= voice == "active"
        path = [child for child in head.children if child.syntax.anchors.get("event") == anchor]
        if len(path) != 1:
            return None
        child, = path
        if any(sibling is not child and sibling.category in {"VP", "VP-NP"}
               for sibling in head.children):
            # A nested coordination/control is not a single owner. Do not
            # project only the first member of a domain we did not prove.
            return None
        overt = _finite_carrier(head, child)
        if overt is not None:
            if carrier is not None:
                return None
            carrier = overt
        head = child
    if not active or head.category != "V":
        return None
    candidate = head.lexical_candidate
    form = "finite" if carrier is None else carrier[1]
    if candidate is None or _values(candidate).get("vform") != form:
        return None
    if any(node.category == "VP-NP" and id(node) not in path_nonfinite for node in _nodes(branch)):
        return None
    # An uninflected stem selected as finite can also be the continuation
    # of a nonfinite coordination. Do not buy that ambiguity in this pilot.
    if carrier is None and candidate.surface.casefold() == candidate.lemma.casefold():
        return None
    return (head,) if carrier is None else (head, carrier[0])


def export_argument_group(
    item: Any, aliases: Mapping[str, str], nodes: Mapping[str, Any],
    args: Mapping[str, Any], *, ambiguous_finite_heads=frozenset(),
) -> ArgumentGroup | None:
    """Resolve exact owner exports and require their declared local proof."""
    proof = args.get("proof")
    if proof not in {"independent_finite_vps", "restrictive_subject_relative"}:
        return None
    names = args["owners"]
    owners = []
    positions = []
    constraints: dict[str, str] = {}
    for name in names:
        links = [link for link in item.syntax.links if link.relation == name]
        owner = aliases.get(name)
        if len(links) != 1 or owner is None:
            return None
        link, = links
        if link.child_index is None or not 0 <= link.child_index < len(item.children):
            return None
        branch = item.children[link.child_index]
        if branch.syntax.anchors.get("event") != link.target:
            return None
        finite_evidence = _independent_finite_head(branch, link.target)
        if finite_evidence is None:
            return None
        head = finite_evidence[0]
        if len(finite_evidence) == 1 and head.lexical_candidate.surface.casefold() in ambiguous_finite_heads:
            return None
        if not _is_anchored(nodes.get(owner), head.start, head.end, kind="event"):
            return None
        for word in (*finite_evidence, branch):
            for key, value in _agreement(word).items():
                if constraints.setdefault(key, value) != value:
                    return None
        positions.append(link.child_index)
        owners.append(owner)
    constraints = tuple(sorted(constraints.items()))
    if proof == "restrictive_subject_relative":
        if positions != [1] or len(item.children) != 2:
            return None
        marker, _ = item.children
        candidate = marker.lexical_candidate
        if (marker.category != "WH-PRONOUN" or candidate is None
                or _values(candidate).get("wh") != "true"
                or candidate.surface.casefold() not in args["marker_forms"]):
            return None
        marker_handle = args["marker"]
        marker_ref = aliases.get(marker_handle)
        if marker_ref is None or not _is_anchored(nodes.get(marker_ref), marker.start, marker.end) or not any(
            link.relation == marker_handle and link.child_index == 0
            and link.target == marker.syntax.anchors.get("referent")
            for link in item.syntax.links
        ):
            return None
        return ArgumentGroup(args["slot"], tuple(owners), constraints, marker=marker_ref)
    # Require distinct ordered direct children and an overt conjunction;
    # the approved evidence is not available for a mere comma or a CP pair.
    if (len(positions) < 2 or positions[0] != 0 or positions[-1] != len(item.children) - 1
            or positions != [i for i, c in enumerate(item.children) if c.category == "VP"]
            or len(set(owners)) != len(owners)):
        return None
    between = item.children[positions[0] + 1:positions[-1]]
    if not any(c.category == "COORD" and _values(c).get("nominal_coordination") == "true"
               for c in between):
        return None
    if any(c.category not in {"COORD", "COMMA", "VP"} for c in between):
        return None
    # Some fallback grammars accept stops/dashes as COMMA. They do not
    # prove that an intervening source clause boundary shares the subject.
    if any(c.category == "COMMA" and (c.lexical_candidate is None or c.lexical_candidate.surface != ",")
           for c in between):
        return None
    return ArgumentGroup(args["slot"], tuple(owners), constraints)


def _is_anchored(node, start, end, *, kind=None):
    return node is not None and node.span == (start, end) and (kind is None or node.kind == kind)


def matches_referent(item: Any, node: Any) -> bool:
    """The semantic filler must be the phrase's actual selected export."""
    anchor = item.syntax.anchors.get("referent", "").split(":", 4)
    if len(anchor) != 5 or anchor[0] != "lex":
        return False
    try:
        start, end = int(anchor[1]), int(anchor[2])
    except ValueError:
        return False
    return item.start <= start < end <= item.end and _is_anchored(node, start, end)


def simple_nominal_filler(item: Any, group: ArgumentGroup) -> bool:
    """Require a simple overt NP and positive subject agreement."""
    if item.category != "NP" or not item.syntax.anchors.get("referent"):
        return False
    agreement = _agreement(item)
    if not {"number", "person"} <= agreement.keys():
        return False
    if any(agreement.get(key) != value for key, value in group.constraints):
        return False
    anchor = item.syntax.anchors["referent"]
    if ":PROPER-NOUN:" in anchor and sum(n.category == "PROPER-NOUN" and not n.children
                                        for n in _nodes(item)) > 1:
        # A first title/name component is not a resolved full-name entity.
        return False
    for node in _nodes(item):
        if (_clause_boundary(node.category)
                or node.category in {"COORD", "COMMA", "COMP-THAT", "VP", "VP-NP", "VP-GAP", "V"}):
            return False
    return True


def argument_edges(
    args: Mapping[str, Any], groups: Sequence[ArgumentGroup], filler: Any, referent: str,
):
    """Produce typed edges without copying another predicate's semantic role."""
    proof = args.get("filler_proof")
    if proof not in {"simple_overt_nominal", "plain_relative_head"}:
        return
    if proof == "plain_relative_head":
        categories = tuple(c.category for c in filler.children)
        if categories not in {("N",), ("PROPER-NOUN",), ("DET", "N"), ("POSS", "N")}:
            return
        if any(c.children for c in filler.children):
            return
    for group in groups:
        if group.slot != args["slot"] or not simple_nominal_filler(filler, group):
            continue
        yield from ((args["relation"], owner, referent) for owner in group.owners)
        if relation := args.get("join_relation"):
            # Keep the existing first-conjunct-headed graph convention.
            yield from ((relation, group.owners[0], right) for right in group.owners[1:])
        if group.marker is not None and (relation := args.get("marker_relation")):
            yield relation, group.marker, referent
