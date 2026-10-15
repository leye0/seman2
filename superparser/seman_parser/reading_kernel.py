"""Experimental event-driven incremental reader: narrow, non-exhaustive microkernel.

This is NOT a general parser yet. It tests whether the grammar's existing
constructions can be recognized through locally expected observations, without
an agenda, beam, dynamic chart, or combinatorial repair. Any unavailable
construction fails explicitly; the kernel must never pretend to cover more.

The rule index is constructed once. Runtime NEVER loops over grammatical rules.
Dependency-injection keeps this state machine independently testable.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ReadingNode:
    category: str
    start: int
    end: int
    rule: Any = None
    children: tuple['ReadingNode', ...] = ()
    candidate: Any = None
    # Semantic relationships are only grammatical obligations, not resolved meaning.
    pending: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReadingEvent:
    action: str
    word: str
    expected: str
    detail: str
    at: int

    def as_dict(self):
        return dict(action=self.action, word=self.word, expected=self.expected,
                    detail=self.detail, at=self.at)


@dataclass
class ReadingOutcome:
    complete: bool
    root: ReadingNode | None
    events: list[ReadingEvent]
    counters: dict[str, int]
    reason: str = ''


class ReaderStopped(Exception):
    pass


class CompiledReactions:
    """Compile reusable constructions by category signatures, not sentence strings.

    These patterns are *capabilities* derived from source rules, not a second
    handwritten grammar. A missing pattern stays unavailable. Multiple rules
    with identical signatures remain alternatives until feature validation.
    """
    def __init__(self, grammar: Any):
        self.index: dict[tuple[str, tuple[str, ...]], tuple[Any, ...]] = {}
        buckets: dict[tuple[str, tuple[str, ...]], list[Any]] = defaultdict(list)
        for rule in grammar.rules:
            buckets[(rule.lhs.category, tuple(s.category for s in rule.rhs))].append(rule)
        self.index = {
            k: tuple(sorted(v, key=lambda rule: (-rule.score, rule.rule_id)))
            for k, v in buckets.items()
        }
        self.compiled_rules = sum(map(len, self.index.values()))
        # Capability detections are structural, not hardcoded sentence templates.
        self.zero_relative = (self.has('NP', 'NP', 'WH-OBJ')
                              and self.has('WH-OBJ', 'NP', 'VP-GAP')
                              and self.has('VP-GAP', 'V'))
        self.nominal_list = (self.has('NP', 'NP', 'COMMA', 'NP')
                             and self.has('NP', 'NP', 'COMMA', 'COORD', 'NP'))
        self.copular_inversion = self.has('CLAUSE', 'COPULA', 'NP', 'PP', 'QMARK')
        self.main_clause = self.has('CLAUSE', 'NP', 'VP')
        # Event-driven reaction dispatch: generated from available grammatical
        # constructions, not from the identities of words in example strings.
        triggers: dict[tuple[str, str], str] = {}
        if self.copular_inversion:
            triggers[('CLAUSE_START', 'COPULA')] = 'COPULAR_INVERSION'
        if self.zero_relative:
            for nominal_signal in ('PROPER-NOUN', 'DET', 'PRONOUN'):
                triggers[('PREDICATE_EXPECTED', nominal_signal)] = 'OBJECT_RELATIVE'
        if self.nominal_list:
            triggers[('NP_COMPLETE', 'COMMA')] = 'NOMINAL_LIST'
        self.triggers = triggers

    def has(self, lhs: str, *rhs: str) -> bool:
        return (lhs, tuple(rhs)) in self.index

    def rules(self, lhs: str, *rhs: str) -> tuple[Any, ...]:
        return self.index.get((lhs, tuple(rhs)), ())


class LocalReader:
    """One interpretation and its immediate expectations; zero speculative parses.

    Input is a sequence of tokens (with start/end/text) and precomputed lexical
    candidates. `combine(rule, children)` may return None when grammatical
    feature unification fails; its invocation counts as an actual calculation.
    """

    def __init__(self, compiled: CompiledReactions,
                 combine: Callable[[Any, tuple[ReadingNode, ...]], ReadingNode | None],
                 tokens: Sequence[Any], candidates: Sequence[Any]):
        self.g = compiled
        self.combine = combine
        self.tokens = tuple(tokens)
        self.pos = 0
        self.by_token: dict[tuple[int, str], list[Any]] = defaultdict(list)
        spans = {(tok.start, tok.end) for tok in self.tokens}
        for item in candidates:
            # Initial indexing O(tokens + lexical candidates), no inner scan.
            # Multiword edges require a future cursor extension.
            if (item.span_start, item.span_end) in spans:
                self.by_token[(item.span_start, item.category)].append(item)
        self.counters = Counter()
        self.events: list[ReadingEvent] = []
        self.suspended: list[str] = []
        self.max_events = max(40, 16 * len(self.tokens))

    def token(self):
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _emit(self, action: str, expected: str, detail: str = ''):
        tok = self.token()
        at = self.pos
        if action == 'COMPLETE' and self.pos:
            at = self.pos - 1
            tok = self.tokens[at]
        if len(self.events) >= self.max_events:
            raise ReaderStopped('event_budget')
        self.events.append(ReadingEvent(action, tok.text if tok else '$END',
                                        expected, detail, self.pos))
        self.counters['events'] += 1

    def _candidates(self, category: str):
        self.counters['category_probes'] += 1
        tok = self.token()
        if tok is None:
            return ()
        return self.by_token.get((tok.start, category), ())

    def _match(self, *categories: str) -> bool:
        return any(self._candidates(c) for c in categories)

    def _reaction(self, context: str) -> str | None:
        """One indexed reaction based on the incoming lexical signal."""
        self.counters['reaction_probes'] += 1
        tok = self.token()
        if tok is None:
            return None
        for (ctx, category), reaction in self.g.triggers.items():
            if ctx == context and (tok.start, category) in self.by_token:
                return reaction
        return None

    @staticmethod
    def _feature(candidate: Any, name: str) -> str | None:
        features = candidate.features
        data = features.as_dict() if hasattr(features, "as_dict") else features
        return str(data[name]) if name in data else None

    def _consume(self, category: str, *, subcat: str | None = None) -> ReadingNode:
        options = self._candidates(category)
        if subcat is not None:
            options = [o for o in options if self._feature(o, "subcat") == subcat]
            self.counters["lexical_feature_checks"] += len(self._candidates(category))
        if not options:
            raise ReaderStopped(f'expected_{category}_at_{self.pos}')
        # One grammatical lexical class, one chosen candidate. No WordNet
        # sense-level branching: syntactically equivalent senses are delayed.
        best = max(options, key=lambda x: x.score)
        tok = self.token()
        assert tok is not None
        self._emit('CONSUME', category, f'{best.lemma}/{best.category}')
        self.counters['consumptions'] += 1
        self.pos += 1
        return ReadingNode(category, tok.start, tok.end, candidate=best)

    def _reduce(self, lhs: str, children: Sequence[ReadingNode]) -> ReadingNode:
        children = tuple(children)
        rhs = tuple(c.category for c in children)
        options = self.g.rules(lhs, *rhs)
        self.counters['rule_lookups'] += 1
        if not options:
            raise ReaderStopped(f'grammar_missing_{lhs}_{rhs}')
        # Distinct productions with SAME category sequence may have distinct
        # feature constraints. Try the finitely many applicable variants here;
        # not a global grammatical search.
        for rule in options:
            self.counters['unifications'] += 1
            result = self.combine(rule, children)
            if result is not None:
                self._emit('COMPLETE', lhs, rule.rule_id)
                self.counters['constructions'] += 1
                return result
        raise ReaderStopped(f'feature_mismatch_{lhs}_{rhs}')

    def _start_np(self) -> ReadingNode:
        self._emit('EXPECT', 'NP', 'nominal head')
        if self._match('DET'):
            det = self._consume('DET')
            modifiers: list[ReadingNode] = []
            while self._match('ADJ'):
                modifiers.append(self._consume('ADJ'))
            n = self._consume('N')
            return self._reduce('NP', (det, *modifiers, n))
        for cat in ('PROPER-NOUN', 'PRONOUN', 'N'):
            if self._match(cat):
                return self._reduce('NP', (self._consume(cat),))
        raise ReaderStopped(f'expected_NP_at_{self.pos}')

    def _nominal(self, *, allow_list: bool = False) -> ReadingNode:
        first = self._start_np()
        if not allow_list or self._reaction('NP_COMPLETE') != 'NOMINAL_LIST':
            return first
        self._emit('EXTEND', 'NP', 'comma announces nominal continuation')
        items = [first]
        separators: list[ReadingNode] = []
        connective = None
        # React to each new comma as it arrives: no materialization of all
        # list arities and no replay of previous items.
        while self._match('COMMA'):
            separators.append(self._consume('COMMA'))
            if self._match('COORD'):
                connective = self._consume('COORD')
                items.append(self._start_np())
                break
            items.append(self._start_np())
        if connective is None:
            if self._match('COORD'):
                connective = self._consume('COORD')
                items.append(self._start_np())
            else:
                # Only build constructions that source grammar licenses.
                node = items[0]
                for sep, nxt in zip(separators, items[1:]):
                    node = self._reduce('NP', (node, sep, nxt))
                return node
        if len(items) == 2 and not separators:
            return self._reduce('NP', (items[0], connective, items[1]))
        if len(items) == 3 and len(separators) == 2:
            # Actual corpus: NP COMMA NP COMMA COORD NP.
            return self._reduce('NP', (items[0], separators[0], items[1],
                                       separators[1], connective, items[2]))
        # For arbitrary length, compose monotonically from left to right.
        node = items[0]
        for sep, nxt in zip(separators[:-1], items[1:-1]):
            node = self._reduce('NP', (node, sep, nxt))
        return self._reduce('NP', (node, separators[-1], connective, items[-1]))

    def _relative_if_signaled(self, head: ReadingNode) -> ReadingNode:
        """A subject-like token where a main predicate is expected may
        signal an unmarked object relative (generic grammar capability).
        Do not preopen this construction after each noun.
        """
        if self._reaction('PREDICATE_EXPECTED') != 'OBJECT_RELATIVE':
            return head
        self._emit('SUSPEND', 'main predicate', 'nominal signal instead of verb')
        self.suspended.append('main predicate')
        subject = self._start_np()
        if not self._match('V'):
            raise ReaderStopped('relative_missing_verb')
        verb = self._consume('V', subcat='transitive')
        vp_gap = self._reduce('VP-GAP', (verb,))
        relative = self._reduce('WH-OBJ', (subject, vp_gap))
        head = self._reduce('NP', (head, relative))
        self.suspended.pop()
        self._emit('RESUME', 'main predicate', 'relative clause completed')
        return head

    def _vp(self) -> ReadingNode:
        self._emit('EXPECT', 'VP', 'finite predicate')
        wants_object = False
        # We decide valence from the *next* lexical category after the V,
        # using a one-token lookahead, never a search through VP rules.
        next_tok = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
        if next_tok is not None:
            wants_object = any((next_tok.start, c) in self.by_token
                               for c in ('DET', 'PROPER-NOUN', 'N', 'PRONOUN'))
        verb = self._consume('V', subcat='transitive' if wants_object else 'intransitive')
        # An NP object is demanded by the observed continuation, not by an
        # ahead-of-time search through the complete verb lexicon.
        if self._match('DET', 'PROPER-NOUN', 'N', 'PRONOUN'):
            obj = self._nominal(allow_list=True)
            return self._reduce('VP', (verb, obj))
        return self._reduce('VP', (verb,))

    def _pp(self) -> ReadingNode:
        self._emit('EXPECT', 'PP', 'preposition + NP')
        prep = self._consume('PREP')
        obj = self._nominal()
        return self._reduce('PP', (prep, obj))

    def _clause(self) -> ReadingNode:
        if self._reaction('CLAUSE_START') == 'COPULAR_INVERSION':
            self._emit('RECOGNIZE', 'CLAUSE', 'inverted copular question')
            copula = self._consume('COPULA')
            subject = self._nominal()
            pred = self._pp()
            end = self._consume('QMARK')
            return self._reduce('CLAUSE', (copula, subject, pred, end))
        if not self.g.main_clause:
            raise ReaderStopped('grammar_missing_main_clause')
        self._emit('RECOGNIZE', 'CLAUSE', 'subject + predicate')
        subject = self._nominal()
        subject = self._relative_if_signaled(subject)
        vp = self._vp()
        return self._reduce('CLAUSE', (subject, vp))

    def read(self) -> ReadingOutcome:
        try:
            root = self._clause()
            # Ordinary punctuation often is not a grammar terminal. QMARK
            # is grammar-driven and consumed inside the inverted question.
            while self.token() is not None and self.token().text in ('.', '!'):
                self._emit('CLOSE', 'punctuation', 'final punctuation')
                self.pos += 1
            if self.pos != len(self.tokens):
                raise ReaderStopped(f'unconsumed_token_{self.pos}')
            self._emit('ACCEPT', '$END', 'all input consumed')
            return ReadingOutcome(True, root, self.events, dict(self.counters))
        except ReaderStopped as exc:
            self._emit('STOP', 'unavailable continuation', str(exc))
            return ReadingOutcome(False, None, self.events, dict(self.counters), str(exc))
