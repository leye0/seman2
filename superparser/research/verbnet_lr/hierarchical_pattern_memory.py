"""Learned hierarchical regular-tree patterns; research-only, no production changes.

A tree-language pattern here is a learned finite set of ORIGINAL grammar
productions with alternatives by LHS and recursion (e.g. NP->NP PP).
Repeated use of a licensed recursive production represents PP* at constituent
level without inventing an unlicensed grammar rule. Optionality corresponds
to an observed base construction AND its recursive extension.

Pattern recognition is a bounded chart with real feature unification for
EVERY reduction. Lexical slots retain all category hypotheses; unrelated
readings never block compatible branches. Memoization shares subconstituents
instead of materializing an exponential list of regex enumerations.

This is a preliminary C engine: chart budget and lexical variant beam are
explicitly reported; semantic correctness is NOT independently certified.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from seman_parser.features import Variable
from seman_parser.predictive import CompactNode, PredictiveParser
from seman_parser.symbols import intern
from research.verbnet_lr.full_structure_snap import Structure


@dataclass(frozen=True, slots=True)
class HierarchicalHit:
    category: str
    start: int
    end: int
    tokens: int
    structurally_novel: bool
    rule_id: str
    score: float


@dataclass(frozen=True, slots=True)
class HierarchicalMatchReport:
    hits: tuple[HierarchicalHit, ...]
    expansions: int
    successful_reductions: int
    incomplete: bool
    elapsed_ms: float
    input_tokens: int

    def longest(self) -> int:
        return max((x.tokens for x in self.hits), default=0)

    def count_at_least(self, length: int, *, novel: bool=False) -> int:
        return sum(h.tokens >= length and (not novel or h.structurally_novel)
                   for h in self.hits)


class HierarchicalPatternMemory:
    """A compact grammar-constrained alternative/repetition network.

    Trains on successful *local grammar reductions*, including reductions
    inside sentences for which parsing the whole CLAUSE failed. Each original
    rule ID needs evidence from >= min_rule_sentences distinct observations
    before it is activated. No synthetic grammar rules are fabricated.
    """

    def __init__(self, resources, *, min_rule_sentences=2,
                 max_span=18, max_rule_arity=4,
                 variants_per_cell=2, max_expansions=12_000,
                 max_wall_ms=150):
        if min(min_rule_sentences,max_span,max_rule_arity,variants_per_cell,
               max_expansions,max_wall_ms)<1:
            raise ValueError("All budgets must be positive")
        self.resources=resources
        self.all_rules={r.rule_id:r for r in resources.grammar.rules}
        self.min_rule_sentences=min_rule_sentences
        self.max_span=max_span
        self.max_rule_arity=max_rule_arity
        self.variants_per_cell=variants_per_cell
        self.max_expansions=max_expansions
        self.max_wall_ms=max_wall_ms
        self.rule_sentence_count=Counter()
        self.shape_sentence_count=Counter()
        self.training_sentences=0
        self.training_failed=0

    @staticmethod
    def shape(node):
        if node.lexical_candidate is not None:
            return Structure(node.category)
        if not node.rule_id:
            raise ValueError("Incomplete node cannot be a pattern witness")
        return Structure(node.category,node.rule_id,
                         tuple(HierarchicalPatternMemory.shape(c)
                               for c in node.children))

    @staticmethod
    def _descend(node):
        if node.lexical_candidate is not None:
            return
        if node.rule_id:
            yield node
        for child in node.children:
            yield from HierarchicalPatternMemory._descend(child)

    def observe(self, items, *, failed: bool, sentence_id: int | None=None):
        seen_rules=set()
        seen_shapes=set()
        for item in items:
            for subtree in self._descend(item):
                seen_rules.add(subtree.rule_id)
                seen_shapes.add(self.shape(subtree))
        for name in seen_rules:
            self.rule_sentence_count[name]+=1
        for shape in seen_shapes:
            self.shape_sentence_count[shape]+=1
        self.training_sentences+=1
        self.training_failed+=int(failed)
        return {"distinct_rules":len(seen_rules),
                "distinct_subtrees":len(seen_shapes),
                "reused_subtree_shapes":sum(self.shape_sentence_count[s]>1
                                             for s in seen_shapes)}

    def active_rules(self):
        return tuple(
            r for key,r in self.all_rules.items()
            if self.rule_sentence_count[key]>=self.min_rule_sentences
            and 1<=len(r.rhs)<=self.max_rule_arity
        )

    def summary(self):
        rules=self.active_rules()
        groups=defaultdict(list)
        for rule in rules:
            groups[rule.lhs.category].append(rule)
        recursive=[]
        optional=[]
        for cat,rows in groups.items():
            rec=[r for r in rows if any(slot.category==cat for slot in r.rhs)]
            base=[r for r in rows if all(slot.category!=cat for slot in r.rhs)]
            if rec:
                recursive.extend(r.rule_id for r in rec)
                if base: optional.append(cat)
        return {
            "training_sentences":self.training_sentences,
            "failed_sentences":self.training_failed,
            "observed_rule_ids":len(self.rule_sentence_count),
            "active_rule_ids":len(rules),
            "alternative_categories":sum(len(v)>=2 for v in groups.values()),
            "recursive_extension_rule_ids":sorted(recursive),
            "root_categories_with_optional_recursive_extension":sorted(optional),
            "distinct_observed_tree_shapes":len(self.shape_sentence_count),
            "budgeted_arity_excluded_rules":sum(
                self.rule_sentence_count[k]>=self.min_rule_sentences
                and len(r.rhs)>self.max_rule_arity
                for k,r in self.all_rules.items()),
        }

    def match(self, lattice, *, min_report_tokens=3, max_span=None):
        """Recognize reusable constituents on ALL lexical alternatives.

        Each reported hit is a newly feature-unified derivation under the
        learned ORIGINAL grammar productions. 'Novel' means that exact
        subtree shape was never observed at training time, not gold-valid.
        """
        begin=perf_counter()
        deadline=begin+self.max_wall_ms/1000
        tokens=tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".","!","?"):
            tokens=tokens[:-1]
        n=len(tokens)
        if n==0:
            return HierarchicalMatchReport((),0,0,False,0,0)
        max_span=min(n,max_span or self.max_span)
        variants=self.variants_per_cell
        rules=self.active_rules()
        by_first=defaultdict(list)
        unary=[]
        for rule in rules:
            if len(rule.rhs)==1: unary.append(rule)
            else: by_first[rule.rhs[0].category].append(rule)

        by_start=defaultdict(list)
        cells=defaultdict(list)
        spans={(t.start,t.end):i for i,t in enumerate(tokens)}
        for candidate in lattice.candidates:
            at=spans.get((candidate.span_start,candidate.span_end))
            if at is None: continue
            evidence=frozenset(k for k,v in candidate.features.items()
                               if not isinstance(v,Variable))
            node=CompactNode(
                candidate.category,intern(candidate.category),
                candidate.span_start,candidate.span_end,
                candidate.features,evidence,candidate.score,
                candidate=candidate)
            # Lexical variants are not restricted by the beam until a
            # genuine grammatical combination is explored.
            by_start[(at,candidate.category)].append((at+1,node))

        # For completed cells use a bounded beam with different rule shapes.
        # It is deliberately an INCOMPLETE recognizer under explicit bounds.
        expansions=0
        successful=0
        incomplete=False
        hits=[]
        seen_hits=set()
        seen_cell_shapes=defaultdict(set)
        # Adding cells modifies by_start, so unary and binary combinations
        # share the same memoized constituent chart.
        def add(start,end,node):
            nonlocal incomplete
            key=(start,end,node.category)
            ident=(node.rule.rule_id if node.rule else "lexical",
                   str(node.features.as_dict()))
            if ident in seen_cell_shapes[key]:
                return False
            if len(cells[key])>=variants:
                incomplete=True
                return False
            seen_cell_shapes[key].add(ident)
            cells[key].append(node)
            if node.rule is not None:
                by_start[(start,node.category)].append((end,node))
                width=end-start
                if width>=min_report_tokens:
                    shape=self._compact_shape(node)
                    hitid=(start,end,node.category,shape)
                    if hitid not in seen_hits:
                        seen_hits.add(hitid)
                        hits.append(HierarchicalHit(
                            node.category,start,end,width,
                            shape not in self.shape_sentence_count,
                            node.rule.rule_id,node.score))
            return True

        halted=False
        for width in range(1,max_span+1):
            if halted:break
            for left in range(n-width+1):
                if halted:break
                right=left+width
                if (perf_counter()>deadline or
                        expansions>=self.max_expansions):
                    incomplete=True;halted=True;break
                if width>=2:
                    # Rules indexed by first grammatical category, not all
                    # productions scanned for each token/window.
                    observed={cat for (at,cat),nodes in by_start.items()
                              if at==left and nodes}
                    for cat in observed:
                        for rule in by_first.get(cat,()):
                            # Ordered contiguous RHS over a bounded span.
                            def choices(i,at,selected):
                                nonlocal expansions,incomplete
                                if expansions>=self.max_expansions or perf_counter()>deadline:
                                    incomplete=True
                                    return
                                if i==len(rule.rhs):
                                    if at!=right:return
                                    expansions+=1
                                    new=PredictiveParser._reduce(rule,tuple(selected))
                                    if new is not None:
                                        nonlocal successful
                                        successful+=1
                                        add(left,right,new)
                                    return
                                rem=len(rule.rhs)-i-1
                                target=rule.rhs[i].category
                                for to,node in tuple(by_start.get((at,target),())):
                                    if to>right-rem or to<=at:
                                        continue
                                    selected.append(node)
                                    yield from choices(i+1,to,selected)
                                    selected.pop()
                            for _ in choices(0,left,[]):
                                pass
                            if expansions>=self.max_expansions:
                                incomplete=True;halted=True;break
                        if halted:break
                # Unary closure is allowed only when the base constituent
                # already exists, with an explicit cycle/budget bound.
                for _ in range(3):
                    added=False
                    for rule in unary:
                        for node in tuple(cells.get((left,right,rule.rhs[0].category),())):
                            if expansions>=self.max_expansions:
                                incomplete=True;halted=True;break
                            expansions+=1
                            result=PredictiveParser._reduce(rule,(node,))
                            if result is not None:
                                successful+=1
                                added |= add(left,right,result)
                        if halted:break
                    if not added or halted:break
        # Filter to strongest constituent for each category/span. The full
        # observed variety is accessible via counters, not claimed as gold.
        filtered={}
        for h in hits:
            key=(h.start,h.end,h.category)
            if key not in filtered or h.score>filtered[key].score:
                filtered[key]=h
        return HierarchicalMatchReport(
            tuple(filtered.values()),expansions,successful,incomplete,
            (perf_counter()-begin)*1000,n)

    @staticmethod
    def _compact_shape(node):
        if node.candidate is not None:
            return Structure(node.category)
        return Structure(node.category,node.rule.rule_id,
                         tuple(HierarchicalPatternMemory._compact_shape(c)
                               for c in node.children))
