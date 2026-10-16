"""Offline feature-checked witness extraction from *packed Earley backpointers*.

In contrast with span-based top-down Cartesian enumeration, this walks
proven predecessor links of a completed Earley goal state. Each concrete
reduction is verified by Seman2's actual PredictiveParser._reduce.

This is a research oracle, never invoked by the incremental L->R runtime.
A missing witness is UNKNOWN, not grammatical rejection, because the packed
backpointer set and derivation search are explicitly bounded.
"""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter

from research.verbnet_lr.upper_bound import recognize_upper_bound
from seman_parser.features import Variable, unify
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.symbols import intern


class _Limit(Exception):
    pass


def _lexical(candidate):
    return CompactNode(
        candidate.category, intern(candidate.category),
        candidate.span_start, candidate.span_end, candidate.features,
        frozenset(k for k, v in candidate.features.items()
                  if not isinstance(v, Variable)), candidate.score,
        candidate=candidate,
    )


def _signature(node):
    candidate = node.candidate
    return (node.grammatical_key(),
            candidate.lemma, candidate.surface,
            repr(candidate.syntactic_constraints))


def _evidence(root, max_depth=9):
    def visit(node, depth):
        if node.candidate is not None:
            return {"category": node.category,
                    "word": node.candidate.surface,
                    "lemma": node.candidate.lemma}
        row = {"category": node.category, "rule": node.rule.rule_id}
        if depth < max_depth:
            row["children"] = [visit(child, depth + 1) for child in node.children]
        else:
            row["children_omitted"] = len(node.children)
        return row
    return visit(root, 0)


def seek_packed_witness(grammar, lattice, *, goal="CLAUSE",
                        max_items=500_000, max_seconds=3.0,
                        max_expansions=100_000, max_paths_per_item=6,
                        max_backpointers=6, validate_tree=None, return_compact_node=False):
    if (max_items < 1 or max_seconds <= 0 or max_expansions < 1
            or max_paths_per_item < 1 or max_backpointers < 1):
        raise ValueError("search budgets must be positive")
    started = perf_counter()
    tokens = tuple(lattice.tokens)
    if tokens and tokens[-1].text in (".", "!"):
        tokens = tokens[:-1]
    n = len(tokens)
    if n == 0:
        return {"status": "UNKNOWN", "reason": "empty_input", "witness": None}

    grammar_rules = [rule for rule in grammar.rules if rule.rhs]
    lexical_by_pos = defaultdict(list)
    lexical_categories = [set() for _ in range(n)]
    span_to_token = {(t.start, t.end): i for i, t in enumerate(tokens)}
    for candidate in lattice.candidates:
        at = span_to_token.get((candidate.span_start, candidate.span_end))
        if at is None:
            continue
        lexical_by_pos[(candidate.category, at)].append(candidate)
        lexical_categories[at].add(candidate.category)

    bound = recognize_upper_bound(
        [(rule.lhs.category, tuple(s.category for s in rule.rhs))
         for rule in grammar_rules], lexical_categories,
        goal=goal, max_items=max_items, max_seconds=max_seconds,
        collect_backpointers=True, max_backpointers=max_backpointers,
    )
    result = {
        "category_status": bound["status"], "category_items": bound["items"],
        "category_ms": bound["elapsed_ms"], "tokens": n,
        "backpointer_truncated": bound.get("backpointer_truncated", False),
    }
    if bound["status"] != "ACCEPTED":
        return {
            **result, "status": "UNKNOWN" if bound["status"] == "UNKNOWN"
            else "CATEGORY_REJECTED",
            "reason": bound["reason"] or "no_category_derivation",
            "witness": None, "feature_expansions": 0,
            "unifications": 0,
        }

    packed = bound["backpointers"]
    deadline = started + max_seconds
    expansions = 0
    unifications = 0
    partial_rejections = 0
    rejected_by_guard = 0
    cutoffs = set()
    if bound["backpointer_truncated"]:
        cutoffs.add("backpointer_limit")
    memo_partial = {}
    memo_complete = {}
    active = set()
    lexical_cache = {}

    def tick():
        nonlocal expansions
        expansions += 1
        if expansions > max_expansions:
            raise _Limit("expansion_budget")
        if expansions % 64 == 0 and perf_counter() > deadline:
            raise _Limit("time_budget")

    def lex_options(category, at):
        key = (category, at)
        if key not in lexical_cache:
            found, seen = [], set()
            for c in sorted(lexical_by_pos[key], key=lambda x: -x.score):
                node = _lexical(c)
                signature = _signature(node)
                if signature in seen:
                    continue
                seen.add(signature)
                found.append(node)
                if len(found) >= max_paths_per_item:
                    cutoffs.add("lexical_limit")
                    break
            lexical_cache[key] = tuple(found)
        return lexical_cache[key]

    def completed(key):
        nonlocal unifications
        tick()
        if key in memo_complete:
            return memo_complete[key]
        tag = ("complete", key)
        if tag in active:
            cutoffs.add("cyclic_derivation")
            return ()
        at, rid, dot, start = key
        rule = grammar_rules[rid]
        if dot != len(rule.rhs):
            return ()
        active.add(tag)
        found = []
        try:
            for children, _env in partial(key):
                tick()
                unifications += 1
                node = PredictiveParser._reduce(rule, children)
                if node is not None:
                    found.append(node)
                    if len(found) >= max_paths_per_item:
                        cutoffs.add("complete_item_limit")
                        break
            memo_complete[key] = tuple(found)
            return memo_complete[key]
        finally:
            active.remove(tag)

    def partial(key):
        nonlocal partial_rejections
        tick()
        if key in memo_partial:
            return memo_partial[key]
        tag = ("partial", key)
        if tag in active:
            cutoffs.add("cyclic_partial_derivation")
            return ()
        _at, rid, dot, _start = key
        if dot == 0:
            return (((), {}),)
        rule = grammar_rules[rid]
        if dot > len(rule.rhs):
            return ()
        active.add(tag)
        found = []
        try:
            slot = rule.rhs[dot - 1]
            for edge in packed.get(key, ()):
                tick()
                earlier = partial(edge[1])
                if edge[0] == "scan":
                    source = lex_options(edge[2], edge[3])
                elif edge[0] == "complete":
                    source = completed(edge[2])
                else:
                    continue
                for siblings, env in earlier:
                    for child in source:
                        tick()
                        if child.category != slot.category:
                            continue
                        if any(intern(req) not in child.evidence
                               for req in slot.requires):
                            partial_rejections += 1
                            continue
                        unified = unify(slot.features, child.features, env)
                        if unified is None:
                            partial_rejections += 1
                            continue
                        found.append((siblings + (child,), unified[1]))
                        if len(found) >= max_paths_per_item:
                            cutoffs.add("partial_item_limit")
                            memo_partial[key] = tuple(found)
                            return memo_partial[key]
            memo_partial[key] = tuple(found)
            return memo_partial[key]
        finally:
            active.remove(tag)

    witness = None
    try:
        for root in bound["roots"]:
            for node in completed(root):
                if validate_tree is None:
                    witness = node
                    break
                check = validate_tree(node)
                if check.acceptable:
                    witness = node
                    break
                rejected_by_guard += 1
            if witness is not None:
                break
    except _Limit as exc:
        cutoffs.add(str(exc))
    report = {
        **result,
        "status": "FOUND" if witness is not None else "UNKNOWN",
        "reason": "" if witness is not None else
                  (",".join(sorted(cutoffs)) if cutoffs else
                   "no_feature_witness_in_selected_packed_paths"),
        "witness": _evidence(witness) if witness is not None else None,
        "feature_expansions": expansions,
        "unifications": unifications,
        "partial_rejections": partial_rejections,
        "guard_rejections": rejected_by_guard,
        "packed_items": len(packed),
        "memo_items": len(memo_partial) + len(memo_complete),
        "feature_ms": round((perf_counter() - started) * 1000
                            - bound["elapsed_ms"], 3),
        "cutoffs": sorted(cutoffs),
    }
    # Research-only internal witness retrieval. Ordinary serialized reports
    # remain JSON-safe and do not retain full derivation objects.
    if return_compact_node:
        report["witness_node"] = witness
    return report
