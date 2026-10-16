"""OFFLINE bounded search for a *concrete, feature-unified* CFG witness.

The permissive Earley recognizer identifies productive category spans first.
Only those spans are explored; every candidate derivation is reduced by
Seman2's *real* PredictiveParser._reduce, including lexical feature evidence.

FOUND supplies an actual unifiable tree, NOT independently annotated syntax.
UNKNOWN means no certified witness within the budget or a pruned ambiguity.
This research tool never changes the L->R parser's runtime decisions.
"""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter

from research.verbnet_lr.upper_bound import recognize_upper_bound
from seman_parser.features import Variable
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.symbols import intern


class _Limit(Exception):
    pass


def _compact(candidate):
    return CompactNode(
        candidate.category, intern(candidate.category),
        candidate.span_start, candidate.span_end, candidate.features,
        frozenset(k for k, val in candidate.features.items()
                  if not isinstance(val, Variable)),
        candidate.score, candidate=candidate,
    )


def _witness_tree(node, depth=0, max_depth=8):
    """A bounded evidence summary, without materializing ChartItems."""
    if node.candidate is not None:
        return {"category": node.category, "surface": node.candidate.surface,
                "lemma": node.candidate.lemma}
    result = {"category": node.category, "rule": node.rule.rule_id}
    if depth < max_depth:
        result["children"] = [_witness_tree(ch, depth + 1, max_depth)
                              for ch in node.children]
    else:
        result["children_omitted"] = len(node.children)
    return result


def seek_feature_witness(grammar, lattice, *, goal="CLAUSE",
                         max_items=500_000, max_seconds=3.0,
                         max_expansions=20_000, max_nodes_per_span=6,
                         validate_tree=None):
    """Try to exhibit one actually unifiable, full-span grammatical tree.

    Bounds are *global*. The algorithm NEVER labels a sentence ungrammatical
    when no witness was found; even a finite exhausted search simply records
    that it found none under its selected candidate projection.
    """
    if max_items < 1 or max_seconds <= 0 or max_expansions < 1 or max_nodes_per_span < 1:
        raise ValueError("all search budgets must be positive")
    started = perf_counter()
    tokens = tuple(lattice.tokens)
    if tokens and tokens[-1].text in (".", "!"):
        tokens = tokens[:-1]
    n = len(tokens)
    if not n:
        return {"status": "UNKNOWN", "reason": "empty_input", "witness": None}
    candidates = defaultdict(list)
    for candidate in lattice.candidates:
        for i, token in enumerate(tokens):
            if candidate.span_start == token.start and candidate.span_end == token.end:
                candidates[(candidate.category, i)].append(candidate)
                break
    lexical = [{category for (category, at) in candidates if at == i} for i in range(n)]
    productions = [(rule.lhs.category, tuple(s.category for s in rule.rhs))
                   for rule in grammar.rules]
    # This step ignores all feature constraints and is an upper bound only.
    bound = recognize_upper_bound(
        productions, lexical, goal=goal, max_items=max_items,
        max_seconds=max_seconds, collect_spans=True)
    base = {"category_status": bound["status"],
            "category_items": bound["items"],
            "category_ms": bound["elapsed_ms"],
            "tokens": n}
    if bound["status"] != "ACCEPTED":
        return {**base, "status": "UNKNOWN" if bound["status"] == "UNKNOWN" else "CATEGORY_REJECTED",
                "reason": bound["reason"] or "no_category_derivation",
                "witness": None, "feature_expansions": 0, "unifications": 0}

    spans = set(bound["spans"])
    for category, at in candidates:
        spans.add((category, at, at + 1))
    ends = defaultdict(list)
    for category, start, end in spans:
        if start < end:
            ends[(category, start)].append(end)
    for key in ends:
        ends[key] = sorted(set(ends[key]))

    by_head = defaultdict(list)
    for rule in grammar.rules:
        if rule.rhs:
            by_head[rule.lhs.category].append(rule)
    for rules in by_head.values():
        rules.sort(key=lambda rule: (-rule.score, rule.rule_id))

    max_deadline = started + max_seconds
    memo = {}
    active = set()
    cutoffs = set()
    expansions = 0
    unifications = 0
    rejected_by_guard = 0
    top_reason = ""

    def step():
        nonlocal expansions
        expansions += 1
        if expansions > max_expansions:
            raise _Limit("expansion_budget")
        if expansions % 64 == 0 and perf_counter() > max_deadline:
            raise _Limit("time_budget")

    def options(category, start, end):
        nonlocal unifications
        step()
        key = (category, start, end)
        if key in memo:
            return memo[key]
        if key in active:
            # A same-span unary cycle can have other derivations. Do not
            # interpret the pruned recursive path as grammatical rejection.
            cutoffs.add("cyclic_same_span_derivation")
            return ()
        if key not in spans:
            return ()
        active.add(key)
        found = []
        try:
            if end == start + 1:
                for cand in sorted(candidates.get((category, start), ()),
                                   key=lambda c: -c.score):
                    step()
                    found.append(_compact(cand))
                    if len(found) >= max_nodes_per_span:
                        cutoffs.add("node_limit_per_span")
                        memo[key] = tuple(found)
                        return memo[key]

            def rhs_sequences(symbols, index, position):
                if index == len(symbols):
                    if position == end:
                        yield ()
                    return
                cat = symbols[index].category
                remaining = len(symbols) - index - 1
                for boundary in ends.get((cat, position), ()):
                    if boundary > end - remaining:
                        break
                    step()
                    for child in options(cat, position, boundary):
                        for rest in rhs_sequences(symbols, index + 1, boundary):
                            yield (child,) + rest

            for rule in by_head[category]:
                step()
                if len(rule.rhs) > end - start:
                    continue
                for children in rhs_sequences(rule.rhs, 0, start):
                    step()
                    unifications += 1
                    node = PredictiveParser._reduce(rule, children)
                    if node is None:
                        continue
                    found.append(node)
                    if len(found) >= max_nodes_per_span:
                        cutoffs.add("node_limit_per_span")
                        memo[key] = tuple(found)
                        return memo[key]
            memo[key] = tuple(found)
            return memo[key]
        finally:
            active.remove(key)

    witness = None
    try:
        for tree in options(goal, 0, n):
            if validate_tree is None:
                witness = tree
                break
            verdict = validate_tree(tree)
            if getattr(verdict, "acceptable", bool(verdict)):
                witness = tree
                break
            rejected_by_guard += 1
            top_reason = getattr(verdict, "reason", "tree_guard_rejected")
    except _Limit as exc:
        cutoffs.add(str(exc))
    result = {
        **base,
        "status": "FOUND" if witness is not None else "UNKNOWN",
        "reason": "" if witness is not None else (
            ",".join(sorted(cutoffs)) if cutoffs else
            (top_reason or "no_feature_unified_witness_found")
        ),
        "feature_expansions": expansions,
        "unifications": unifications,
        "guard_rejections": rejected_by_guard,
        "feature_ms": round((perf_counter() - started) * 1000
                            - bound["elapsed_ms"], 3),
        "candidate_spans": len(memo),
        "cutoffs": sorted(cutoffs),
        "witness": _witness_tree(witness) if witness is not None else None,
    }
    return result
