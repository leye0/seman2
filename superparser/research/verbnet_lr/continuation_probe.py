"""Bounded, read-only structural continuation estimator for Seman2.

The compiled index contains optimistic FIRST-category closure and the first
two grammar RHS slots. A two-token lookahead is a *heuristic*: the first
constituent may span many tokens. No category/feature is ever pruned.
No forest, derivation, k-best materialization, or recognition is created.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from math import log2
from time import perf_counter_ns

from seman_parser.features import unify


@dataclass(frozen=True)
class RuleStart:
    index: int
    symbol: object
    direct: bool
    skeleton: tuple


class ContinuationIndex:
    def __init__(self, grammar):
        rules=tuple(grammar)
        self.rule_count=len(rules)
        # Grammatically derived category -> possible first lexical category.
        # Include the category itself conservatively (e.g. lexical NP).
        cats={r.lhs.category for r in rules}
        cats.update(s.category for r in rules for s in r.rhs)
        first={c:{c} for c in cats}
        while True:
            changed=False
            for r in rules:
                if not r.rhs:
                    continue
                old=len(first[r.lhs.category])
                first[r.lhs.category].update(first[r.rhs[0].category])
                changed|=len(first[r.lhs.category])!=old
            if not changed:
                break
        self.first={k:frozenset(v) for k,v in first.items()}
        start=defaultdict(list)
        follow=defaultdict(list)
        self.skeletons={}
        self.rule_ids={}
        for idx,rule in enumerate(rules):
            if not rule.rhs:
                continue
            self.rule_ids[idx]=rule.rule_id
            skeleton=(rule.lhs.category,tuple(s.category for s in rule.rhs))
            self.skeletons[idx]=skeleton
            for cat in self.first[rule.rhs[0].category]:
                start[cat].append(RuleStart(
                    idx,rule.rhs[0],cat==rule.rhs[0].category,skeleton))
            if len(rule.rhs)>1:
                for cat in self.first[rule.rhs[1].category]:
                    follow[cat].append(RuleStart(
                        idx,rule.rhs[1],cat==rule.rhs[1].category,skeleton))
        self.start={k:tuple(v) for k,v in start.items()}
        self.follow={k:tuple(v) for k,v in follow.items()}
        self.skeleton_count=len(set(self.skeletons.values()))
        self.compiler_slots=sum(len(v) for v in self.start.values())+sum(
            len(v) for v in self.follow.values())
        # Category-only bitset automaton: compile once, then union compatible
        # rule starts with cheap OR operations. Original rule variants remain
        # represented by separate bits (no grammar information deleted).
        skeleton_ids={shape:i for i,shape in enumerate(
            sorted(set(self.skeletons.values())))}
        self.fast_start={}
        self.fast_follow={}
        self.fast_skeleton={}
        for category,slots in self.start.items():
            mask=0
            skeleton_mask=0
            for slot in slots:
                mask|=1<<slot.index
                skeleton_mask|=1<<skeleton_ids[slot.skeleton]
            self.fast_start[category]=mask
            self.fast_skeleton[category]=skeleton_mask
        for category,slots in self.follow.items():
            mask=0
            for slot in slots:
                mask|=1<<slot.index
            self.fast_follow[category]=mask

    def fast_signal(self,lattice):
        """Cheap upper-bound structural risk, without feature unification.

        This estimates category-compatible rule fanout only. It must never
        be used to prune, and indirect FIRST spans are still approximate.
        """
        start=perf_counter_ns()
        grouped=defaultdict(set)
        for candidate in lattice.candidates:
            grouped[(candidate.span_start,candidate.span_end)].add(candidate.category)
        start_masks=[]
        follow_masks=[]
        start_counts=[]
        excess=0
        for token in lattice.tokens:
            categories=grouped.get((token.start,token.end),())
            first=second=skels=0
            for category in categories:
                first|=self.fast_start.get(category,0)
                second|=self.fast_follow.get(category,0)
                skels|=self.fast_skeleton.get(category,0)
            start_masks.append(first)
            follow_masks.append(second)
            n=first.bit_count()
            start_counts.append(n)
            excess+=n-skels.bit_count()
        pairs=[
            (a & b).bit_count()
            for a,b in zip(start_masks,follow_masks[1:])
        ]
        result={
            "fast_start_sum":sum(start_counts),
            "fast_start_peak":max(start_counts,default=0),
            "fast_pair_sum":sum(pairs),
            "fast_pair_peak":max(pairs,default=0),
            "fast_variant_excess":excess,
            "fast_pair_log_sum":round(sum(log2(1+n) for n in pairs),5),
        }
        result["fast_probe_ms"]=(perf_counter_ns()-start)/1e6
        return result

    @staticmethod
    def _matches(slot, candidates):
        # Direct lexical category: a *necessary* feature compatibility check.
        # Indirect category through FIRST closure: do not incorrectly unify
        # the lexical leaf features with a higher phrase node.
        for c in candidates:
            if not slot.direct or unify(slot.symbol.features,c.features) is not None:
                return True
        return False

    def _viable(self, candidates, lookup):
        bycat=defaultdict(list)
        for c in candidates:
            bycat[c.category].append(c)
        matched=set()
        for cat,choices in bycat.items():
            for slot in lookup.get(cat,()):
                if slot.index not in matched and self._matches(slot,choices):
                    matched.add(slot.index)
        return matched

    def signal(self,lattice):
        before=perf_counter_ns()
        grouped=defaultdict(list)
        for c in lattice.candidates:
            grouped[(c.span_start,c.span_end)].append(c)
        # Explicit exact-token options only: multiword edges are tracked
        # separately, not silently interpreted as individual token options.
        sets=[tuple(grouped[(t.start,t.end)]) for t in lattice.tokens]
        first_sets=[self._viable(group,self.start) for group in sets]
        second_sets=[self._viable(group,self.follow) for group in sets]
        starts=[len(items) for items in first_sets]
        pairs=[first_sets[i].intersection(second_sets[i+1])
               for i in range(max(0,len(sets)-1))]
        pair_counts=[len(x) for x in pairs]
        compressed=[
            len({self.skeletons[k] for k in items}) for items in first_sets
        ]
        # Count alternatives without accidentally treating no lexical leaf
        # as a proof that any parse is valid or impossible.
        result={
            "struct_start_sum":sum(starts),
            "struct_start_peak":max(starts,default=0),
            "struct_pair_sum":sum(pair_counts),
            "struct_pair_peak":max(pair_counts,default=0),
            "struct_pair_log_sum":round(
                sum(log2(1+n) for n in pair_counts),5),
            "struct_variant_excess":sum(a-b for a,b in zip(starts,compressed)),
            "struct_zero_leaf_tokens":sum(not group for group in sets),
            "struct_pair_positions":sum(n>0 for n in pair_counts),
            "struct_nonexact_spans":sum(
                span not in {(t.start,t.end) for t in lattice.tokens}
                for span in grouped),
        }
        result["struct_probe_ms"]=(perf_counter_ns()-before)/1e6
        return result
