"""Provisional reusable grammar subtrees recovered from completed L-R reductions.

A failed CLAUSE may still have locally unified NP, VP, PP, etc. Such
reductions are *candidate evidence*, NOT global syntactic gold.
At lookup a proposed subtree is reassembled from new lexical candidates
through the original grammar/unifier. Never cache raw token strings.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from research.verbnet_lr.full_structure_snap import (
    FullStructureSnapIndex, _leaf_categories,
)
from seman_parser.segmentation import LexicalLattice


@dataclass(frozen=True)
class ReuseReport:
    compatible_windows: int
    grammar_validated_windows: int
    checked_templates: int
    incomplete: bool
    covered_tokens: int
    matched_spans: tuple[tuple[int, int, str], ...]


class PartialStructureMemory:
    def __init__(self, resources: Any, *, min_tokens=2, max_tokens=12,
                 max_templates=50_000):
        if min_tokens<1 or max_tokens<min_tokens or max_templates<1:
            raise ValueError("Invalid partial-store limits")
        self.resources=resources
        self.min_tokens=min_tokens
        self.max_tokens=max_tokens
        self.max_templates=max_templates
        self.indexes={}
        self.signatures=defaultdict(set)
        self.observations=Counter()
        self.totals=Counter()
        self.seen_shapes=set()
        self.global_root_counts=Counter()
        self._fingerprint_index=set()

    def _window(self, lattice, start, end):
        return LexicalLattice(lattice.text, tuple(lattice.tokens[start:end]),
                              lattice.candidates)

    def _select(self, item, lattice):
        tokens=lattice.tokens
        start=next((i for i,t in enumerate(tokens) if t.start==item.start),None)
        end=next((i+1 for i,t in enumerate(tokens) if t.end==item.end),None)
        if start is None or end is None or end<=start:
            return None
        width=end-start
        if not self.min_tokens<=width<=self.max_tokens:
            return None
        return start,end

    def observe(self, partial_items, lattice, *, sentence_id, failed):
        """Learn each distinct actually-unified derivation once per sentence.

        Failed enclosing sentence does not confer a verification label.
        Repeated observations from different sentences are counted exactly;
        repeated nested copies from the same sentence do not inflate rates.
        """
        local=set()
        repeated=False
        unique_added=0
        for item in partial_items:
            segment=self._select(item,lattice)
            if segment is None:
                self.totals["outside_length_or_not_aligned"]+=1
                continue
            start,end=segment
            cat=item.category
            index=self.indexes.get(cat)
            if index is None:
                index=FullStructureSnapIndex(
                    self.resources,goal=cat,max_templates=self.max_templates)
                self.indexes[cat]=index
            try:
                shape=index._shape(item)
            except (ValueError,KeyError):
                self.totals["invalid_shape"]+=1
                continue
            # Multiple reductions with same shape in one sentence still
            # constitute a single source-sentence observation.
            if shape in local:
                continue
            local.add(shape)
            known=(cat,shape) in self.seen_shapes
            if known:
                repeated=True
                self.totals["reused_partial_observations"]+=1
                if failed:
                    self.totals["reused_on_failed_sentences"]+=1
            else:
                if sum(len(i.templates) for i in self.indexes.values())>=self.max_templates:
                    self.totals["capacity_exhausted"]+=1
                    continue
                self.seen_shapes.add((cat,shape))
                unique_added+=1
            window=self._window(lattice,start,end)
            try:
                index.observe(item,lattice=window,evidence="candidate")
            except (ValueError,OverflowError):
                self.totals["rejected_by_index"]+=1
                if not known: self.seen_shapes.discard((cat,shape))
                continue
            self.signatures[(end-start,cat)].add(_leaf_categories(shape))
            self.global_root_counts[cat]+=1
            self.totals["partial_source_observations"]+=1
            if failed:
                self.totals["partial_sources_from_failed_sentences"]+=1
        self.totals["sentences_with_partial_evidence"]+=int(bool(local))
        self.totals["sentences_with_reused_partial"]+=int(repeated)
        if failed:
            self.totals["failed_sentences_with_partial_evidence"]+=int(bool(local))
            self.totals["failed_sentences_with_reused_partial"]+=int(repeated)
        return {"unique_added":unique_added,
                "repeated":repeated,"source_shapes":len(local)}

    def match(self,lattice, *, max_validations=128,
              max_templates_checked=128):
        """Revalidate candidate subtrees on NEW lexical material.

        A candidate category sequence merely schedules a real grammar
        unification. A failed unifier never produces a reported match.
        """
        tokens=tuple(lattice.tokens)
        if tokens and tokens[-1].text in (".","!","?"):
            tokens=tokens[:-1]
        spans={(t.start,t.end):i for i,t in enumerate(tokens)}
        slots=[set() for _ in tokens]
        for c in lattice.candidates:
            i=spans.get((c.span_start,c.span_end))
            if i is not None:
                slots[i].add(c.category)
        compatible=validated=checked=0
        incomplete=False
        matches=[]
        covered=set()
        # Shorter windows get tested first, but every successful verified
        # window is counted and overlapping constituent spans are retained.
        for (width,cat), patterns in sorted(self.signatures.items()):
            if width>len(tokens):
                continue
            for start in range(len(tokens)-width+1):
                window_slots=slots[start:start+width]
                if not all(window_slots):
                    continue
                if not any(all(c in choices for c,choices in zip(pattern,window_slots))
                           for pattern in patterns):
                    continue
                compatible+=1
                if checked>=max_validations:
                    incomplete=True
                    continue
                checked+=1
                index=self.indexes[cat]
                window=LexicalLattice(lattice.text,tokens[start:start+width],
                                      lattice.candidates)
                result=index.match(window,max_templates_checked=max_templates_checked,
                                   max_states=4096,max_variants=8,max_reductions=512)
                incomplete |= result.incomplete
                if result.complete:
                    validated+=1
                    matches.append((start,start+width,cat))
                    covered.update(range(start,start+width))
        return ReuseReport(
            compatible,validated,checked,incomplete,len(covered),
            tuple(matches))

    def summary(self):
        templates=sum(len(index.templates) for index in self.indexes.values())
        return {
            "unique_complete_subtree_shapes":templates,
            "unique_leaf_category_sequences_by_root":sum(len(v) for v in self.signatures.values()),
            "root_counts":dict(self.global_root_counts),
            "counters":dict(self.totals),
            "lengths_indexed":sorted({n for n,_ in self.signatures}),
        }
