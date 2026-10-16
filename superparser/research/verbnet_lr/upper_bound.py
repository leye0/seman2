"""Conservative CFG *upper-bound* recognizer for offline grammar research.

This is NOT Seman2's production or L->R parser. It ignores morphological and
semantic unification, scores, selectional restrictions and lexical senses.
It accepts a productive grammar category as EITHER a direct lexical candidate
or the LHS of a rule, mirroring the compiled reader's dual lexical categories.

Meaning: REJECTED with full search is proof of missing *category-level*
coverage in this grammar/lattice; ACCEPTED is NOT proof of a valid parse.
Timeout/item-budget must be reported as UNKNOWN, never as rejection.
"""
from __future__ import annotations

from collections import defaultdict, deque
from time import perf_counter


class _Budget(Exception):
    pass


def recognize_upper_bound(rules, categories, *, goal="CLAUSE",
                          max_items=200_000, max_seconds=2.5,
                          collect_spans=False):
    """Boolean Earley recognition with no materialized parse trees.

    :param rules: iterable of (lhs_category, tuple(rhs_categories)).
    :param categories: one collection of observed lexical POS per token.
    All terminals, including productive categories like N, can scan directly.
    """
    productions = [(lhs, tuple(rhs)) for lhs, rhs in rules if rhs]
    by_lhs = defaultdict(list)
    for idx, (lhs, _rhs) in enumerate(productions):
        by_lhs[lhs].append(idx)
    observed = tuple(frozenset(cats) for cats in categories)
    n = len(observed)
    chart = [set() for _ in range(n + 1)]
    agenda = [deque() for _ in range(n + 1)]
    waiting = [defaultdict(list) for _ in range(n + 1)]
    predicted = [set() for _ in range(n + 1)]
    deadline = perf_counter() + max_seconds
    begun = perf_counter()
    count = 0
    furthest_goal = 0
    completed_spans = set() if collect_spans else None

    def add(at, item):
        nonlocal count
        if item in chart[at]:
            return
        if count >= max_items:
            raise _Budget("item_budget")
        chart[at].add(item)
        agenda[at].append(item)
        count += 1

    status = "REJECTED"
    try:
        if goal not in by_lhs:
            return {"status": "REJECTED", "complete": False,
                    "reason": "goal_has_no_rules", "items": 0,
                    "furthest_goal_prefix": 0, "elapsed_ms": 0.0}
        for idx in by_lhs[goal]:
            add(0, (idx, 0, 0))
        for at in range(n + 1):
            while agenda[at]:
                if count % 128 == 0 and perf_counter() > deadline:
                    raise _Budget("time_budget")
                rule_idx, dot, start = agenda[at].popleft()
                lhs, rhs = productions[rule_idx]
                if dot == len(rhs):
                    if completed_spans is not None:
                        completed_spans.add((lhs, start, at))
                    if lhs == goal and start == 0:
                        furthest_goal = max(furthest_goal, at)
                        if at == n:
                            # Recognition is existential. Stop on the first
                            # full-span derivation; exploring other trees
                            # wastes the item budget and can turn an already
                            # demonstrated ACCEPT into UNKNOWN.
                            return {
                                "status": "ACCEPTED",
                                "complete": True,
                                "reason": "",
                                "items": count,
                                "furthest_goal_prefix": n,
                                "elapsed_ms": round((perf_counter() - begun) * 1000, 3),
                                "max_chart_items": max(map(len, chart)),
                                **({"spans": frozenset(completed_spans)}
                                   if completed_spans is not None else {}),
                            }
                    for parent_idx, parent_dot, parent_start in waiting[start][lhs]:
                        add(at, (parent_idx, parent_dot + 1, parent_start))
                    continue
                symbol = rhs[dot]
                waiting[at][symbol].append((rule_idx, dot, start))
                if symbol in by_lhs and symbol not in predicted[at]:
                    predicted[at].add(symbol)
                    for child_idx in by_lhs[symbol]:
                        add(at, (child_idx, 0, at))
                if at < n and symbol in observed[at]:
                    add(at + 1, (rule_idx, dot + 1, start))
        reason = ""
    except _Budget as exc:
        status = "UNKNOWN"
        reason = str(exc)
    return {
        "status": status,
        "complete": True if status == "ACCEPTED" else (
            False if status == "REJECTED" else None),
        "reason": reason,
        "items": count,
        "furthest_goal_prefix": furthest_goal,
        "elapsed_ms": round((perf_counter() - begun) * 1000, 3),
        "max_chart_items": max(map(len, chart)),
        **({"spans": frozenset(completed_spans)}
           if completed_spans is not None else {}),
    }
