"""Seman2 reading-kernel V1: grammar-compiled single-continuation reader.

No chart, beam, recursive candidate enumeration, search queue, or production
fallback. Compilation factorizes RHS prefixes into tries. At runtime a token's
lexical category dispatches directly to one grammar transition; completed
phrases may be extended by grammar-licensed direct left-recursive rules.

Deliberately incomplete: a wrong commitment reports STOP; this is *not* an
exhaustive CFG recognizer. Semantic gaps aren't resolved by this core.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence


@dataclass(frozen=True)
class ReadNode:
    category: str
    start: int
    end: int
    rule: Any = None
    children: tuple['ReadNode', ...] = ()
    candidate: Any = None
    alternatives: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Event:
    at: int
    word: str
    action: str
    expected: str
    detail: str

    def as_dict(self):
        return vars(self).copy()


@dataclass
class Outcome:
    complete: bool
    root: ReadNode | None
    events: list[Event]
    counters: dict[str, int]
    reason: str = ''


class Stop(Exception):
    pass


class State:
    __slots__ = ('edges', 'finals', 'dispatch', 'priority', 'state_id', 'hints')

    def __init__(self, state_id: int):
        self.edges: dict[str, State] = {}
        self.finals: list[Any] = []
        self.dispatch: dict[str, tuple[str, ...]] = {}
        self.priority = -1e5
        self.state_id = state_id
        self.hints: dict[str, list[tuple[Any, Any, tuple[str, ...]]]] = defaultdict(list)


class CompiledGrammar:
    """Compile once: FIRST sets + common-prefix tries + lexical dispatch.

    Direct left recursion is compiled as an *extension* after a constituent
    is complete (NP -> NP WH-OBJ, NP -> NP COMMA NP, etc.). There is no
    speculative expansion of these rules.
    """
    def __init__(self, grammar: Any):
        rules = list(grammar.rules)
        self.nonterminals = {r.lhs.category for r in rules}
        self.roots: dict[str, State] = {}
        self.extensions: dict[str, State] = {}
        self.by_signature: dict[tuple[str, tuple[str, ...]], tuple[Any, ...]] = {}
        self.first: dict[str, frozenset[str]] = {}
        self.first_depth: dict[str, dict[str, int]] = {}
        self.producers: dict[str, list[Any]] = defaultdict(list)
        self._next_id = 0
        self.states: list[State] = []
        signatures: dict[tuple[str, tuple[str, ...]], list[Any]] = defaultdict(list)
        initial = self.producers
        ext: dict[str, list[Any]] = defaultdict(list)
        for rule in rules:
            rhs = tuple(s.category for s in rule.rhs)
            signatures[(rule.lhs.category, rhs)].append(rule)
            if rhs and rhs[0] == rule.lhs.category:
                ext[rule.lhs.category].append(rule)
            elif rhs:
                initial[rule.lhs.category].append(rule)
        self.by_signature = {k: tuple(sorted(v, key=lambda r: (-r.score, r.rule_id)))
                             for k, v in signatures.items()}
        # Compute FIRST ignoring directly left-recursive productions (their
        # FIRST depends on an already recognized left-hand constituent).
        # A category may simultaneously be a lexical category and the LHS of
        # productive rules: e.g. N -> ADJ N, N -> N N.  FIRST(N) must
        # include an incoming lexical N, not solely expansions such as ADJ.
        # Starting with self-categories is safe: the actual input lattice
        # decides whether a direct lexical token exists at runtime.
        first = {name: {name} for name in self.nonterminals}
        for _ in range(len(self.nonterminals) + 1):
            modified = False
            for name, candidates in initial.items():
                for rule in candidates:
                    symbol = rule.rhs[0].category
                    values = first[symbol] if symbol in first else {symbol}
                    before = len(first[name]); first[name].update(values)
                    modified |= len(first[name]) != before
            if not modified:
                break
        self.first = {key: frozenset(val) for key, val in first.items()}
        # Distance to an observed lexical category, computed once.
        depth = {name: {name: 0} for name in self.nonterminals}
        for _ in range(len(self.nonterminals) + 1):
            changed = False
            for name, items in initial.items():
                for rule in items:
                    cat = rule.rhs[0].category
                    for lexical, steps in depth.get(cat, {cat: 0}).items():
                        cost = steps + 1
                        if cost < depth[name].get(lexical, 10**9):
                            depth[name][lexical] = cost
                            changed = True
            if not changed:
                break
        self.first_depth = depth
        for name, items in initial.items():
            self.roots[name] = self._make_trie(items, drop_head=False)
        for name, items in ext.items():
            self.extensions[name] = self._make_trie(items, drop_head=True)
        for node in self.states:
            dispatch: dict[str, list[str]] = defaultdict(list)
            for symbol, successor in node.edges.items():
                for lexical in self._first_compatible_with_hints(symbol, node.hints.get(symbol, ())):
                    dispatch[lexical].append(symbol)
            # A precomputed, compact map; no rule enumeration per input word.
            node.dispatch = {
                lexical: tuple(sorted(syms, key=lambda sym: (
                    -node.edges[sym].priority,
                    0 if sym not in self.nonterminals else 1, sym)))
                for lexical, syms in dispatch.items()
            }
        self.stats = {
            'grammar_rules': len(rules),
            'prefix_states': len(self.states),
            'initial_categories': len(self.roots),
            'extendable_categories': len(self.extensions),
        }

    def _first_compatible_with_hints(self, category, hints):
        """Compile the lexical starts of an RHS slot, including its positive
        feature requirements. No grammar scan happens during reading.
        """
        if category not in self.nonterminals:
            return frozenset((category,))
        starts = set()
        for _, expected, _ in hints:
            wanted = expected.features.as_dict() if hasattr(expected.features, 'as_dict') else expected.features
            proof = set(getattr(expected, 'requires', ()))
            if not proof and not any(not str(v).startswith('?') for v in wanted.values()):
                starts.update(self.first.get(category, ()))
                continue
            # Direct lexical child of this category can still satisfy it;
            # its actual features are checked when consumed.
            starts.add(category)
            for rule in self.producers.get(category, ()):
                produced = rule.lhs.features.as_dict() if hasattr(rule.lhs.features, 'as_dict') else rule.lhs.features
                if not proof.issubset(produced):
                    continue
                if any(key in produced and not str(value).startswith('?')
                       and not str(produced[key]).startswith('?')
                       and produced[key] != value for key, value in wanted.items()):
                    continue
                head = rule.rhs[0].category
                starts.update(self.first.get(head, (head,)))
        return frozenset(starts)

    def _state(self):
        obj = State(self._next_id)
        self._next_id += 1
        self.states.append(obj)
        return obj

    def _make_trie(self, rules, *, drop_head):
        root = self._state()
        for rule in rules:
            cur = root
            cur.priority = max(cur.priority, rule.score)
            for idx, sym in enumerate(rule.rhs[int(drop_head):]):
                remainder = tuple(s.category for s in rule.rhs[int(drop_head) + idx + 1:])
                cur.hints[sym.category].append((rule, sym, remainder))
                if sym.category not in cur.edges:
                    cur.edges[sym.category] = self._state()
                cur = cur.edges[sym.category]
                cur.priority = max(cur.priority, rule.score)
            cur.finals.append(rule)
        for node in self._descendants(root):
            node.finals.sort(key=lambda r: (-r.score, r.rule_id))
        return root

    @staticmethod
    def _descendants(root):
        stack = [root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node.edges.values())


class IncrementalReader:
    """One active continuation, emitted events match actual operations.

    A child is finished before its caller resumes. `stop_at` lets the caller
    retain ownership of delimiters (e.g., commas inside a larger list).
    """
    def __init__(self, compiled: CompiledGrammar,
                 combine: Callable[[Any, tuple[ReadNode, ...]], ReadNode | None],
                 tokens: Sequence[Any], candidates: Sequence[Any], *, goal: str = 'CLAUSE',
                 compiled_lookahead: int = 1):
        self.g = compiled
        self.combine = combine
        self.tokens = tuple(tokens)
        self.goal = goal
        if compiled_lookahead not in (1, 2, 3):
            raise ValueError('compiled_lookahead must be 1, 2 or 3')
        self.compiled_lookahead = compiled_lookahead
        self.pos = 0
        self.events: list[Event] = []
        self.count = Counter()
        self.lex: dict[int, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
        spans = {(token.start, token.end): i for i, token in enumerate(self.tokens)}
        for candidate in candidates:
            i = spans.get((candidate.span_start, candidate.span_end))
            if i is not None:
                # This single-sentence reader owns the final stop itself
                # (see read()). A lexical COMMA analysis of '.' or '!'
                # must not masquerade as a grammatical VP continuation.
                # Keep '?' available: question rules consume QMARK.
                if self.tokens[i].text in ('.', '!'):
                    continue
                self.lex[i][candidate.category].append(candidate)
        self.lex_cats = tuple(frozenset(self.lex[i]) for i in range(len(self.tokens)))
        self._min_yield = {}
        self._remaining_tokens = ()
        self._lookahead_cache = {}
        if self.compiled_lookahead >= 2:
            self._prepare_bounded_lookahead()
        self.active: set[tuple[str, int]] = set()
        self.depth = 0
        self.limit = max(96, 30 * len(self.tokens))

    def _prepare_bounded_lookahead(self):
        """Per-sentence lower bounds from compiled rules; no parse search.

        A lexical category appearing in the input consumes one token.
        A constructed category can only consume at least the sum of its RHS
        minimums. No manually maintained class/word list is involved.
        """
        remaining = [0] * (len(self.tokens) + 1)
        for at in range(len(self.tokens) - 1, -1, -1):
            remaining[at] = remaining[at + 1] + int(bool(self.lex_cats[at]))
        self._remaining_tokens = tuple(remaining)
        mins = {cat: 1 for cats in self.lex_cats for cat in cats}
        signatures = tuple(self.g.by_signature)
        # Terminal categories always have minimum lexical yield one even
        # when absent from this particular sentence. Otherwise PP might
        # incorrectly look unbounded simply because no PREP is present.
        for _, rhs in signatures:
            for cat in rhs:
                if cat not in self.g.nonterminals:
                    mins[cat] = 1
        for _ in range(len(self.g.nonterminals) + 1):
            changed = False
            for lhs, rhs in signatures:
                if not all(cat in mins for cat in rhs):
                    continue
                cost = sum(mins[cat] for cat in rhs)
                if cost < mins.get(lhs, 10 ** 7):
                    mins[lhs] = cost
                    changed = True
            if not changed:
                break
        self._min_yield = mins

    def _min_yield_available(self, symbol, at):
        minimum = self._min_yield.get(symbol)
        return minimum is None or (
            at < len(self._remaining_tokens)
            and self._remaining_tokens[at] >= minimum
        )

    def _two_token_witness(self, category, at):
        """Direct evidence for an initial lexical slot + following slot.

        Probe only a compiled category trie and two observed token positions.
        No tree is built. Unknown does not mean impossible; it simply lacks
        the bonus. Memoized per category/position for a sentence.
        """
        key = (category, at)
        if key in self._lookahead_cache:
            return self._lookahead_cache[key]
        self.count['two_token_probes'] += 1
        root = self.g.roots.get(category)
        if root is None or at + 1 >= len(self.tokens):
            self._lookahead_cache[key] = False
            return False
        for first_cat in self._categories(at):
            for first in root.dispatch.get(first_cat, ()):
                # A constructed first slot may occupy several tokens, so do
                # not conjecture its end. Only direct lexical first slots
                # yield a positive two-token witness.
                if not self._lexical_compatible(first, root.hints.get(first, ()), at=at):
                    continue
                child = root.edges[first]
                for second_cat in self._categories(at + 1):
                    for second in child.dispatch.get(second_cat, ()):
                        if second in self.g.nonterminals:
                            if self._min_yield_available(second, at + 1):
                                self._lookahead_cache[key] = True
                                self.count['two_token_witnesses'] += 1
                                return True
                        elif self._lexical_compatible(
                                second, child.hints.get(second, ()), at=at + 1):
                            self._lookahead_cache[key] = True
                            self.count['two_token_witnesses'] += 1
                            return True
        self._lookahead_cache[key] = False
        return False

    def _edge_second_token_witness(self, state: State, at: int) -> bool:
        """A directly observed next-token transition, no parse or search."""
        key = ('edge', state.state_id, at)
        previous = self._lookahead_cache.get(key)
        if previous is not None:
            return previous
        self.count['edge_witness_probes'] += 1
        found = False
        for lexical in self._categories(at):
            for symbol in state.dispatch.get(lexical, ()):
                if symbol in self.g.nonterminals:
                    if self._min_yield_available(symbol, at):
                        found = True
                        break
                elif self._lexical_compatible(symbol, state.hints.get(symbol, ()), at=at):
                    found = True
                    break
            if found:
                break
        self._lookahead_cache[key] = found
        if found:
            self.count['edge_witness_hits'] += 1
        return found

    def _emit(self, action, expected, detail='', *, at=None):
        at = self.pos if at is None else at
        tok = self.tokens[at] if at < len(self.tokens) else None
        self.events.append(Event(at, tok.text if tok else '$END', action, expected, detail))
        self.count['events'] += 1
        if self.count['events'] > self.limit:
            raise Stop('event_budget')

    def _categories(self, at=None):
        at = self.pos if at is None else at
        return self.lex_cats[at] if at < len(self.lex_cats) else frozenset()

    def _matches(self, cat, at=None):
        self.count['category_checks'] += 1
        return bool(self.g.first.get(cat, frozenset()) & self._categories(at)) if cat in self.g.nonterminals else cat in self._categories(at)

    @staticmethod
    def _value_compatible(expected, observed):
        """Check a typed lexical feature against a grammar constraint.

        A disjunctive lexical feature licenses any of its constituent atoms.
        The final production reduction still uses Seman2's full unifier.
        """
        if isinstance(expected, str) and expected.startswith('?'):
            return True
        if isinstance(observed, str) and observed.startswith('?'):
            return True
        if isinstance(observed, (list, tuple, set, frozenset)):
            return any(IncrementalReader._value_compatible(expected, one)
                       for one in observed)
        if isinstance(expected, (list, tuple, set, frozenset)):
            return any(IncrementalReader._value_compatible(one, observed)
                       for one in expected)
        if isinstance(expected, dict) and isinstance(observed, dict):
            return all(k not in observed or IncrementalReader._value_compatible(v, observed[k])
                       for k, v in expected.items())
        return expected == observed

    def _lexical_compatible(self, category: str, hints=(), *, at=None) -> bool:
        """Check actual lexical evidence *before* committing to an edge.

        Does not spawn parses or unify semantic structures. A candidate only
        needs to satisfy one compiled RHS projection. If an edge's lexical
        evidence contradicts every production, it cannot win by score.
        """
        at = self.pos if at is None else at
        options = self.lex[at].get(category, ()) if at < len(self.tokens) else ()
        if not options:
            return False
        if not hints:
            return True
        for candidate in options:
            attrs = self._features(candidate)
            for _rule, symbol, _remaining in hints:
                required = self._features(symbol)
                if any(key in attrs and not self._value_compatible(value, attrs[key])
                       for key, value in required.items()):
                    continue
                if any(key not in attrs for key in getattr(symbol, 'requires', ())):
                    continue
                return True
        return False

    def _local_continuation(self, state: State, at: int) -> int:
        """One-token viability of a COMPILED state; no recursive search.

        A prefix completed now is immediately viable. Otherwise, only an
        indexed next lexical category counts as evidence. This is a single
        bounded observation, not simulated parsing of candidate branches.
        """
        if state.finals:
            return 2
        if at >= len(self.tokens):
            return 0
        candidates = self._categories(at)
        for category in candidates:
            for symbol in state.dispatch.get(category, ()):
                if symbol in self.g.nonterminals:
                    return 1
                if self._lexical_compatible(symbol, state.hints.get(symbol, ()), at=at):
                    return 1
        return 0

    def _select(self, state: State, live=None, *, excluded=frozenset()):
        self.count['dispatches'] += 1
        # Dispatch only by *observed lexical categories*. No rule listing,
        # no DFS, and at most one next-token check per distinct transition.
        paths: list[str] = []
        seen = set()
        for category in self._categories():
            for symbol in state.dispatch.get(category, ()):
                if symbol not in seen and symbol not in excluded:
                    seen.add(symbol)
                    paths.append(symbol)
        self.count['eligible_transitions'] += len(paths)
        if not paths:
            return None

        ranked = []
        for symbol in paths:
            self.count['local_evidence_checks'] += 1
            target = state.edges[symbol]
            hints = tuple(h for h in state.hints.get(symbol, ())
                          if live is None or id(h[0]) in live)
            if not hints:
                continue
            direct = self._lexical_compatible(symbol, hints)
            if symbol not in self.g.nonterminals and not direct:
                continue
            if (self.compiled_lookahead >= 2 and symbol in self.g.nonterminals
                    and not direct and not self._min_yield_available(symbol, self.pos)):
                self.count['min_yield_rejections'] += 1
                continue
            # A productive category can ALSO be lexical (N, ADJ, etc.).
            # If a compatible token exists, prefer consuming it directly.
            # Otherwise the category may be opened as a constructed child.
            # Direct reads must still check whether the *following* word
            # can continue this compiled rule or complete the prefix.
            support = (self._local_continuation(target, self.pos + 1)
                       if direct else
                       1 if symbol in self.g.nonterminals else 0)
            if (self.compiled_lookahead >= 2 and symbol in self.g.nonterminals
                    and not direct and self._two_token_witness(symbol, self.pos)):
                # A productive two-token construction has more evidence than
                # a one-token ellipsis. This is a *ranking*, not hard pruning.
                support = 3
            if (self.compiled_lookahead == 3 and direct
                    and self._edge_second_token_witness(target, self.pos + 1)):
                # Reward a direct lexical reading whose compiled rule can
                # also consume the next word. A passive AUX-BE V competes
                # with COPULA ADJP using the existing rule scores.
                support = max(support, 3)
            if support == 0:
                continue
            distance = min(
                self.g.first_depth.get(symbol, {}).get(c, 10**6)
                for c in self._categories()
            ) if symbol in self.g.nonterminals else 0
            ranked.append((support,
                           1 if symbol not in self.g.nonterminals else 0,
                           -distance, max(r.score for r, _, _ in hints), symbol))
        if not ranked:
            return None
        return max(ranked)[-1]

    @staticmethod
    def _features(item):
        features = getattr(item, 'features', {})
        return features.as_dict() if hasattr(features, 'as_dict') else features

    def _lexical_rank_bonus(self, candidate, category: str) -> int:
        """Optional lexical evidence: only a tie-breaker, never an obligation.

        The baseline returns zero for every candidate. Research readers may
        override the hook, but grammatical compatibility and viability always
        take precedence. No second parsing algorithm is invoked.
        """
        return 0

    def _consume(self, category: str, hints=()):
        self.count['lexical_lookups'] += 1
        options = self.lex[self.pos].get(category, ())
        if not options:
            raise Stop(f'expected_{category}_at_{self.pos}')
        # A lexical candidate is preferred for the *next construction actually
        # expected*, not merely because its WordNet sense has a high score.
        # This is a tiny indexed projection of RHS feature constraints, not a
        # search over all possible parses or lexical-sense combinations.
        next_categories = self._categories(self.pos + 1)
        selected = None
        best_rank = None
        for candidate in options:
            attrs = self._features(candidate)
            bonus = None  # one lexical hint per candidate, not per rule
            for rule, symbol, tail in hints:
                required = self._features(symbol)
                if any(key in attrs and not self._value_compatible(value, attrs[key])
                       for key, value in required.items()):
                    continue
                if any(key not in attrs for key in getattr(symbol, 'requires', ())):
                    continue
                tail_expected = bool(tail and (
                    self.g.first.get(tail[0], frozenset()) & next_categories if
                    tail[0] in self.g.nonterminals else tail[0] in next_categories))
                # Prefer a rule's continuation if the NEXT token confirms it.
                # Avoid preferring an unfinished rule when the next token
                # cannot possibly begin its next slot.
                viable = 2 if tail_expected else (1 if not tail else 0)
                if bonus is None:
                    bonus = self._lexical_rank_bonus(candidate, category)
                rank = (viable, rule.score, bonus, candidate.score)
                self.count['lexical_feature_checks'] += 1
                if best_rank is None or rank > best_rank:
                    selected, best_rank = candidate, rank
        if selected is None:
            # Lexical ambiguity unsupported by known RHS projections.
            # Never pretend a candidate satisfies a positive requirement.
            if hints:
                raise Stop(f'lexical_features_incompatible_{category}_at_{self.pos}')
            selected = max(options, key=lambda candidate: candidate.score)
        start = self.pos
        self._emit('CONSUME', category, f'{selected.lemma}/{selected.category}')
        self.pos += 1
        self.count['consumptions'] += 1
        return ReadNode(category, selected.span_start, selected.span_end,
                        candidate=selected, alternatives=tuple(options))

    def _slot_candidate(self, child, slot):
        """Bind lexical ambiguity to a real rule slot, never to a prefix union."""
        if child.candidate is None:
            return child if child.category == slot.category else None
        required = self._features(slot)
        valid = [c for c in (child.alternatives or (child.candidate,))
                 if (all(k not in self._features(c) or
                         self._value_compatible(v, self._features(c)[k])
                         for k, v in required.items())
                     and all(k in self._features(c)
                             for k in getattr(slot, 'requires', ())))]
        if not valid:
            return None
        choice = max(valid, key=lambda c: c.score)
        return child if choice is child.candidate else ReadNode(
            child.category, child.start, child.end,
            candidate=choice, alternatives=child.alternatives)

    def _reduce(self, category, children, rules):
        if not rules:
            raise Stop(f'no_grammar_completion_{category}_at_{self.pos}')
        children = tuple(children)
        self.count['rule_signature_lookups'] += 1
        for r in rules:  # only productions retained by the active-rule mask
            bound = tuple(self._slot_candidate(ch, slot)
                          for ch, slot in zip(children, r.rhs))
            if len(bound) != len(children) or any(ch is None for ch in bound):
                continue
            self.count['unifications'] += 1
            node = self.combine(r, bound)
            if node is not None:
                self.count['lexical_rebindings'] += sum(
                    a is not b for a, b in zip(bound, children))
                last = max(0, self.pos - 1)
                self._emit('COMPLETE', category, r.rule_id, at=last)
                self.count['completions'] += 1
                return node
        raise Stop(f'unification_failed_{category}_at_{self.pos}')

    def _parse(self, category, stop_at=frozenset()):
        key = (category, self.pos)
        if key in self.active:
            raise Stop(f'nonconsuming_recursive_{category}_at_{self.pos}')
        if category not in self.g.roots:
            raise Stop(f'grammar_has_no_entry_{category}_at_{self.pos}')
        self.active.add(key)
        self.depth += 1
        self.count['max_stack_depth'] = max(self.count['max_stack_depth'], self.depth)
        self._emit('EXPECT', category, f'compiled state {self.g.roots[category].state_id}')
        try:
            node = self._walk(category, self.g.roots[category])
            # An extension is *not even consulted* unless the next token can
            # start its compiled suffix, and the caller has not reserved it.
            root = self.g.extensions.get(category)
            while root and self.pos < len(self.tokens):
                if self._categories() & stop_at:
                    break
                sym = self._select(root)
                if sym is None:
                    break
                self.count['extensions'] += 1
                self._emit('EXTEND', category, f'compiled suffix at {root.state_id}')
                node = self._walk(category, root, seed=node)
            return node
        finally:
            self.active.remove(key)
            self.depth -= 1

    def _walk(self, category, root, seed=None):
        state = root
        children = [seed] if seed is not None else []
        live = None  # compact set of still-compatible production identities
        steps = 0
        while True:
            steps += 1
            if steps > len(self.tokens) * 3 + 4:
                raise Stop('nonprogressing_continuation')
            edge = self._select(state, live)
            if state.finals and edge is not None:
                # A complete constituent may extend. Do not commit to a
                # longer rule if its imminent terminal lookahead contradicts
                # the actual next token (e.g., COMMA COORD vs COMMA NOUN).
                if not self._viable(state.edges[edge], self.pos + 1):
                    edge = None
            if edge is None:
                finals = (state.finals if live is None else
                          [r for r in state.finals if id(r) in live])
                if finals:
                    return self._reduce(category, children, finals)
                raise Stop(f'expected_continuation_{category}_at_{self.pos}_state_{state.state_id}')
            target = state.edges[edge]
            hints = tuple(h for h in state.hints.get(edge, ())
                          if live is None or id(h[0]) in live)
            direct = self._lexical_compatible(edge, hints)
            if edge in self.g.nonterminals and not direct:
                # Only open a productive category when no lexical candidate
                # directly satisfies the requested category and constraints.
                # The parent retains ownership of upcoming delimiters.
                # Réserver uniquement les symboles explicites du parent,
                # pas les FIRST des sous-constructions qu'il pourrait ouvrir.
                boundary = set(target.dispatch)
                extension = self.g.extensions.get(edge)

                # Une coordination peut prolonger le constituant enfant,
                # sauf si le parent attend explicitement COORD.
                if (extension is not None
                        and 'COORD' in extension.edges
                        and 'COORD' not in target.edges):
                    boundary.discard('COORD')
                self.count['nonterminal_opens'] += 1
                child = self._parse(edge, boundary)
            else:
                # When this token cannot be followed by any licensed
                # continuation, its lexical reading must support a rule
                # which COMPLETES the current prefix.  Do not allow a
                # higher-scored reading from an unfinished construction to
                # win and then fail at the immediate reduction.
                if target.finals and not (self._categories(self.pos + 1) & target.dispatch.keys()):
                    final_ids = {id(rule) for rule in target.finals}
                    closing_hints = tuple(
                        (rule, symbol, tail)
                        for rule, symbol, tail in hints
                        if not tail and id(rule) in final_ids
                    )
                    if closing_hints:
                        hints = closing_hints
                child = self._consume(edge, hints)
            # Once a slot is read, discard grammatically impossible rules.
            # Lexical alternatives remain available until actual reduction.
            live = frozenset(id(rule) for rule, slot, _ in hints
                             if self._slot_candidate(child, slot) is not None)
            if not live:
                raise Stop(f'no_live_rule_{category}_at_{self.pos}')
            self.count['active_rule_filters'] += 1
            children.append(child)
            state = target

    def _viable(self, state, at):
        """Cheap bounded *terminal* lookahead, never a tree or search.

        If a complete prefix could end now, disallow committing to an
        extension that immediately demands absent punctuation / conjunction.
        Nonterminal categories only check FIRST and stop lookahead.
        """
        if state.finals:
            return True
        if at >= len(self.tokens):
            return False
        for symbol, next_state in state.edges.items():
            self.count['lookahead_checks'] += 1
            if self._matches(symbol, at):
                if symbol in self.g.nonterminals:
                    return True
                return self._viable(next_state, at + 1)
        return False

    def read(self):
        root = None
        try:
            root = self._parse(self.goal)
            while self.pos < len(self.tokens) and self.tokens[self.pos].text in ('.', '!'):
                self._emit('CLOSE', 'punctuation', 'sentence end')
                self.pos += 1
            if self.pos < len(self.tokens):
                raise Stop(f'unconsumed_{self.pos}_{self.tokens[self.pos].text}')
            self._emit('ACCEPT', self.goal, 'input consumed')
            return Outcome(True, root, self.events, dict(self.count))
        except Stop as exc:
            self._emit('STOP', self.goal, str(exc))
            return Outcome(False, None, self.events, dict(self.count), str(exc))
