"""Coreference evaluation: match mentions to gold, score with B³ and LEA.

Gold mentions are ``(sentence_index, surface, occurrence)`` tuples. System
mentions come from :class:`~seman_parser.reader.DiscourseProcessor`. Matching
is by sentence + normalized surface + occurrence, so the scorer does not
depend on character spans (system spans are often over-wide NPs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .discourse import Mention


@dataclass(frozen=True)
class GoldMention:
    sentence_index: int
    surface: str
    occurrence: int
    entity_id: str

    @property
    def key(self) -> tuple[int, str, int]:
        return (self.sentence_index, _norm(self.surface), self.occurrence)


def _norm(surface: str) -> str:
    return " ".join(surface.strip().lower().split())


def build_gold_index(
    chains: Mapping[str, Sequence[tuple[int, str, int]]],
) -> dict[tuple[int, str, int], GoldMention]:
    """Map (sent, surface_norm, occurrence) -> gold mention."""
    out: dict[tuple[int, str, int], GoldMention] = {}
    for entity_id, mentions in chains.items():
        for sent, surface, occ in mentions:
            gm = GoldMention(sent, surface, occ, entity_id)
            out[gm.key] = gm
    return out


def match_system_mentions(
    gold_index: Mapping[tuple[int, str, int], GoldMention],
    system_mentions: Sequence[Mention],
) -> dict[tuple[int, str, int], tuple[GoldMention, Mention | None]]:
    """For each gold mention, find a system mention in the same sentence.

    Exact surface match first (by occurrence). If none, accept a containment
    match (``home`` ⊂ ``at home``) so scoring is not only about mention
    boundaries. System occurrence counts repeats of a normalized surface
    inside one sentence in extraction order.
    """
    seen: dict[tuple[int, str], int] = {}
    by_key: dict[tuple[int, str, int], Mention] = {}
    by_sent: dict[int, list[tuple[str, Mention]]] = {}
    for m in system_mentions:
        surf = _norm(m.surface)
        k0 = (m.sentence_index, surf)
        occ = seen.get(k0, 0)
        seen[k0] = occ + 1
        by_key[(m.sentence_index, surf, occ)] = m
        by_sent.setdefault(m.sentence_index, []).append((surf, m))

    matched: dict[tuple[int, str, int], tuple[GoldMention, Mention | None]] = {}
    for key, gm in gold_index.items():
        exact = by_key.get(key)
        if exact is not None:
            matched[key] = (gm, exact)
            continue
        # containment: shortest system surface that contains the gold tokens
        gold_toks = set(gm.surface.lower().split())
        best: Mention | None = None
        best_len = 10**9
        for surf, m in by_sent.get(gm.sentence_index, []):
            if not gold_toks:
                continue
            sys_toks = set(surf.split())
            if gold_toks <= sys_toks or (sys_toks and sys_toks <= gold_toks):
                if len(surf) < best_len:
                    best, best_len = m, len(surf)
        matched[key] = (gm, best)
    return matched


def _clusters_from_keys(
    items: Iterable[tuple[tuple[int, str, int], str]],
) -> dict[str, set[tuple[int, str, int]]]:
    """entity_id -> set of mention keys."""
    out: dict[str, set[tuple[int, str, int]]] = {}
    for key, eid in items:
        out.setdefault(eid, set()).add(key)
    return out


def b3(
    gold_clusters: Mapping[str, set],
    system_clusters: Mapping[str, set],
    mention_keys: set,
) -> tuple[float, float, float]:
    """Bag-of-words B³ precision / recall / F1 over ``mention_keys``."""
    gold_of = {m: e for e, ms in gold_clusters.items() for m in ms if m in mention_keys}
    sys_of = {m: e for e, ms in system_clusters.items() for m in ms if m in mention_keys}

    keys = sorted(mention_keys & gold_of.keys() & sys_of.keys())
    if not keys:
        return 0.0, 0.0, 0.0

    p_sum = r_sum = 0.0
    for m in keys:
        g = gold_clusters[gold_of[m]]
        s = system_clusters[sys_of[m]]
        inter = len(g & s)
        p_sum += inter / len(s) if s else 0.0
        r_sum += inter / len(g) if g else 0.0
    p = p_sum / len(keys)
    r = r_sum / len(keys)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def lea(
    gold_clusters: Mapping[str, set],
    system_clusters: Mapping[str, set],
    mention_keys: set,
) -> tuple[float, float, float]:
    """Link-based Entity-Aware (LEA) precision / recall / F1.

    For each entity, link score = correctly linked mentions / possible links.
    Importance of an entity = number of mentions. See Moosavi & Strube 2016.
    """
    gold_of = {m: e for e, ms in gold_clusters.items() for m in ms if m in mention_keys}
    sys_of = {m: e for e, ms in system_clusters.items() for m in ms if m in mention_keys}
    keys = sorted(mention_keys & gold_of.keys() & sys_of.keys())
    if not keys:
        return 0.0, 0.0, 0.0

    def link_score(entity_mentions: set, other_of: Mapping, other_clusters: Mapping) -> float:
        ms = [m for m in entity_mentions if m in other_of]
        n = len(entity_mentions)
        if n <= 1:
            return 1.0
        correct = 0
        for i, m in enumerate(ms):
            for j in range(i + 1, len(ms)):
                m2 = ms[j]
                # correct link if the other partition puts them together
                # or both are missing from the other partition's known set
                e1 = other_of.get(m)
                e2 = other_of.get(m2)
                if e1 is not None and e2 is not None:
                    if e1 == e2:
                        correct += 1
                # unlinked in other partition counts as wrong for LEA recall
        possible = n * (n - 1) / 2
        return correct / possible if possible else 1.0

    # Recall: gold entities, links recovered by system
    r_num = r_den = 0.0
    for eid, ms in gold_clusters.items():
        g_ms = {m for m in ms if m in mention_keys}
        if not g_ms:
            continue
        imp = len(g_ms)
        # links among gold mentions that the system also saw
        seen = [m for m in g_ms if m in sys_of]
        if len(g_ms) <= 1:
            score = 1.0
        else:
            correct = 0
            for i, m in enumerate(g_ms):
                for m2 in list(g_ms)[i + 1 :]:
                    e1 = sys_of.get(m)
                    e2 = sys_of.get(m2)
                    if e1 is not None and e2 is not None and e1 == e2:
                        correct += 1
            possible = len(g_ms) * (len(g_ms) - 1) / 2
            score = correct / possible if possible else 1.0
        r_num += imp * score
        r_den += imp
    recall = r_num / r_den if r_den else 0.0

    # Precision: system entities, links correct vs gold
    p_num = p_den = 0.0
    for eid, ms in system_clusters.items():
        s_ms = {m for m in ms if m in mention_keys and m in gold_of}
        if not s_ms:
            continue
        imp = len(s_ms)
        if len(s_ms) <= 1:
            score = 1.0
        else:
            correct = 0
            keys_l = list(s_ms)
            for i, m in enumerate(keys_l):
                for m2 in keys_l[i + 1 :]:
                    if gold_of.get(m) is not None and gold_of.get(m) == gold_of.get(m2):
                        correct += 1
            possible = len(s_ms) * (len(s_ms) - 1) / 2
            score = correct / possible if possible else 1.0
        p_num += imp * score
        p_den += imp
    precision = p_num / p_den if p_den else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


@dataclass
class EvalReport:
    matched: int
    unmatched_gold: list[tuple[int, str, int, str]]
    b3_p: float
    b3_r: float
    b3_f1: float
    lea_p: float
    lea_r: float
    lea_f1: float
    chains_system: Mapping[str, list[str]]
    chains_gold: Mapping[str, list[tuple[int, str, int]]]

    def summary(self) -> str:
        lines = [
            f"mentions gold matched: {self.matched}/{self.matched + len(self.unmatched_gold)}",
            f"B3   P={self.b3_p:.3f} R={self.b3_r:.3f} F1={self.b3_f1:.3f}",
            f"LEA  P={self.lea_p:.3f} R={self.lea_r:.3f} F1={self.lea_f1:.3f}",
        ]
        if self.unmatched_gold:
            lines.append("unmatched gold:")
            for sent, surface, occ, eid in self.unmatched_gold:
                lines.append(f"  S{sent} {surface!r}#{occ} [{eid}]")
        return "\n".join(lines)


def evaluate(
    gold_chains: Mapping[str, Sequence[tuple[int, str, int]]],
    system_mentions: Sequence[Mention],
    system_entity_of: Mapping[str, str],
) -> EvalReport:
    """Score system coreference against gold chains.

    ``system_entity_of`` maps mention_id -> entity_id (may include None-valued
    links already committed by ``link_best``).
    """
    gold_index = build_gold_index(gold_chains)
    matched = match_system_mentions(gold_index, system_mentions)

    mention_keys: set = set()
    gold_clusters: dict[str, set] = {}
    sys_clusters: dict[str, set] = {}
    unmatched: list[tuple[int, str, int, str]] = []

    # index system mentions by key for entity lookup
    seen: dict[tuple[int, str], int] = {}
    sys_by_key: dict[tuple[int, str, int], Mention] = {}
    for m in system_mentions:
        k0 = (m.sentence_index, _norm(m.surface))
        occ = seen.get(k0, 0)
        seen[k0] = occ + 1
        sys_by_key[(m.sentence_index, _norm(m.surface), occ)] = m

    for key, (gm, sm) in matched.items():
        gold_clusters.setdefault(gm.entity_id, set()).add(key)
        if sm is None:
            unmatched.append((gm.sentence_index, gm.surface, gm.occurrence, gm.entity_id))
            continue
        mention_keys.add(key)
        eid = system_entity_of.get(sm.mention_id)
        if eid is None:
            # new-entity commit: each unmatched mention is its own system cluster
            eid = f"new:{sm.mention_id}"
        sys_clusters.setdefault(eid, set()).add(key)

    # gold clusters should only contain matched keys for fair B3/LEA,
    # but LEA recall uses full gold entity size — keep all gold keys in gold_clusters
    for key, gm in gold_index.items():
        gold_clusters.setdefault(gm.entity_id, set()).add(key)

    scored_keys = mention_keys
    b3_p, b3_r, b3_f1 = b3(gold_clusters, sys_clusters, scored_keys)
    lea_p, lea_r, lea_f1 = lea(gold_clusters, sys_clusters, scored_keys)

    return EvalReport(
        matched=len(mention_keys),
        unmatched_gold=unmatched,
        b3_p=b3_p,
        b3_r=b3_r,
        b3_f1=b3_f1,
        lea_p=lea_p,
        lea_r=lea_r,
        lea_f1=lea_f1,
        chains_system={e: sorted(ms) for e, ms in sys_clusters.items()},
        chains_gold={e: list(ms) for e, ms in gold_chains.items()},
    )
