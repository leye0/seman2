"""Reusable grammatical tree plans with NO parsing on a remembered hit.

Training stores a full immutable Structure tree and compiles the rule feature
constraints into leaf-slot checks. Replay uses the positional inverted index,
fills lexical slots, checks precompiled feature equalities, and returns an
occurrence pointing at the SAME tree. It does NOT call _reduce, _materialize,
a parser, or rebuild any grammar nodes.

Only atomic/variable feature constraints and safely checkable RHS evidence are
currently compiled. Complex structures, disjunctions, unsupported evidence,
and exhausted candidate budgets are DEFERRED to the existing parser, never
asserted to be valid snaps. This is deliberately conservative.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from collections import defaultdict
from typing import Any

from seman_parser.features import Atom, Variable, Disjunction, FeatureStructure, TOP
from seman_parser.symbols import intern
from .full_structure_snap import FullStructureSnapIndex, Structure, Template
from .positional_template_index import PositionalTemplateIndex


@dataclass(frozen=True, slots=True)
class CompiledSlot:
    category: str
    checks: tuple[tuple[tuple[int, ...], int], ...]  # (feature path, equality group)
    requires: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompiledPlan:
    structure: Structure  # immutable and SHARED, never cloned at replay
    slots: tuple[CompiledSlot, ...]
    constants: tuple[tuple[int, int], ...]  # (group, interned atom)
    rules: tuple[str, ...]
    token_category_groups: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledOccurrence:
    """Ready for a future Layer 2 adapter; NOT a ChartItem/ParseResult."""
    structure_id: int
    structure: Structure
    original_text: str
    tokens: tuple[Any, ...]
    lexical_slots: tuple[Any, ...]
    lexical_alternatives: tuple[tuple[Any, ...], ...]
    plan: CompiledPlan
    feature_bindings: tuple[tuple[int, object], ...]

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(candidate.surface for candidate in self.lexical_slots)


@dataclass(frozen=True, slots=True)
class CompiledReplay:
    occurrence: CompiledOccurrence | None
    candidate_templates: int
    checked_templates: int
    incomplete: bool
    reason: str

    @property
    def complete(self) -> bool:
        return self.occurrence is not None


class _Union:
    def __init__(self):
        self.parent = {}
        self.value = {}
        self.conflict = False

    def root(self, key):
        if key not in self.parent:
            self.parent[key] = key
        x = key
        while self.parent[x] != x:
            x = self.parent[x]
        while key != x:
            old = self.parent[key]
            self.parent[key] = x
            key = old
        return x

    def join(self, left, right):
        a, b = self.root(left), self.root(right)
        if a == b:
            return
        av, bv = self.value.get(a), self.value.get(b)
        if av is not None and bv is not None and av != bv:
            self.conflict = True
        self.parent[b] = a
        if av is None and bv is not None:
            self.value[a] = bv

    def constant(self, key, value):
        a = self.root(key)
        previous = self.value.get(a)
        if previous is not None and previous != value:
            self.conflict = True
        self.value[a] = value


def compile_plan(shape: Structure, rules: dict[str, Any], *, token_groups=None) -> CompiledPlan | None:
    """Precompile the entire rule graph to equality groups once, on observe.

    A variable name is local to the RULE OCCURRENCE, not global to the tree.
    Shared child attribute nodes connect interfaces across rule boundaries.
    No lexical value from the training sentence is copied into this plan.
    """
    union = _Union()
    leaves = []
    evidence = {}
    rule_ids = []
    serial = 0
    unsupported = False

    def attach(node_id, features, rule_instance, prefix=()):
        nonlocal unsupported
        for attr, value in features.items():
            path=prefix+(attr,)
            key = ("node", node_id, path)
            if isinstance(value, FeatureStructure):
                # Flatten nested agreement/feature structures at compile time.
                attach(node_id,value,rule_instance,path)
            elif isinstance(value, Atom):
                union.constant(key, value.symbol)
            elif isinstance(value, Variable):
                union.join(key, ("var", rule_instance, value.name))
            elif value is TOP:
                continue
            else:
                # A grammar disjunction is not a universal constraint;
                # defer if not yet compilable, never quietly ignore it.
                unsupported = True

    def visit(node):
        nonlocal serial, unsupported
        node_id = serial
        serial += 1
        if node.rule_id is None:
            leaves.append((node_id, node.category))
            return node_id
        rule = rules.get(node.rule_id)
        if rule is None or rule.lhs.category != node.category or len(node.children) != len(rule.rhs):
            unsupported = True
            return node_id
        rule_ids.append(rule.rule_id)
        attach(node_id, rule.lhs.features, node_id)
        for child, symbol in zip(node.children, rule.rhs):
            if symbol.category != child.category:
                unsupported = True
            child_id = visit(child)
            attach(child_id, symbol.features, node_id)
            if symbol.requires:
                if child.rule_id is not None:
                    # RHS evidence on a nonlexical child depends on grammar
                    # exports; do not treat it as a simple leaf check.
                    unsupported = True
                else:
                    evidence.setdefault(child_id,set()).update(intern(k) for k in symbol.requires)
        return node_id

    visit(shape)
    if unsupported or union.conflict or not leaves:
        return None

    # Turn arbitrary node-variable DSU keys into dense group IDs and
    # pre-resolve all grammar constants.
    roots = {union.root(key) for key in union.parent}
    group_by_root = {root: i for i,root in enumerate(sorted(roots,key=repr))}
    constants = tuple(sorted(
        (group_by_root[union.root(key)], value)
        for key,value in union.value.items()
        if union.root(key)==key
    ))
    checks_by_node={}
    for key in union.parent:
        if key[0]=="node":
            checks_by_node.setdefault(key[1],[]).append((
                key[2],group_by_root[union.root(key)]))
    slots=tuple(
        CompiledSlot(category,tuple(sorted(checks_by_node.get(leaf_id,()))),
                     tuple(sorted(evidence.get(leaf_id,()))))
        for leaf_id,category in leaves
    )
    if token_groups is None:
        token_groups=tuple((slot.category,) for slot in slots)
    return CompiledPlan(shape,slots,constants,tuple(rule_ids),tuple(token_groups))


class CompiledStructureReplayer:
    """Structure learning then direct indexed replay, returning a word overlay."""

    def __init__(self, resources, *, max_templates=20_000_000):
        self.index = FullStructureSnapIndex(resources,max_templates=max_templates)
        self.plans: list[CompiledPlan | None] = []
        # One token may legitimately contain several grammatical leaves
        # (contractions, possessives). Keep a separate indexed morphology
        # pattern: categories of every lexical segment within each token.
        self._segmented_index = PositionalTemplateIndex()
        self._segmented_by_signature = {}

    @staticmethod
    def _source_token_groups(item,lattice):
        """Exact lexical coverage, allowing multiple leaves per token.

        Unlike the old validator, a contraction may yield two separate
        leaves inside one token. No missing, overlapping, or fabricated
        word parts can be silently indexed.
        """
        leaves=[]
        def collect(node):
            if node.lexical_candidate is not None:
                leaves.append((node.start,node.end,node.category))
            else:
                for child in node.children:
                    collect(child)
        collect(item)
        tokens=tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".","!","?"):
            tokens=tokens[:-1]
        groups=[]
        cursor=0
        for tok in tokens:
            boundary=tok.start
            categories=[]
            while cursor<len(leaves) and leaves[cursor][0]<tok.end:
                start,end,category=leaves[cursor]
                if start!=boundary or end>tok.end or end<=start:
                    raise ValueError("Cannot index noncontiguous or overlapping lexical leaves")
                categories.append(category)
                boundary=end
                cursor+=1
            if not categories or boundary!=tok.end:
                raise ValueError("A word in the sentence has no grammatical lexical leaf")
            groups.append(tuple(categories))
        if cursor!=len(leaves):
            raise ValueError("Lexical tree has leaves outside the sentence tokens")
        return tuple(groups)

    def observe(self, item, *, lattice, evidence="candidate") -> int:
        groups=self._source_token_groups(item,lattice)
        shape=self.index._shape(item)
        segmented=any(len(group)!=1 for group in groups)
        if not segmented:
            key=self.index.observe(item,lattice=lattice,evidence=evidence)
            if key==len(self.plans):
                self.plans.append(compile_plan(
                    self.index.templates[key].shape,self.index.rules,
                    token_groups=groups))
            return key
        signature=(shape,groups)
        prior=self._segmented_by_signature.get(signature)
        if prior is not None:
            self.index.templates[prior].candidate_observations+=1
            return prior
        if len(self.index.templates)>=self.index.max_templates:
            raise OverflowError("Template capacity reached")
        key=len(self.index.templates)
        self._segmented_by_signature[signature]=key
        self.index.templates.append(Template(
            shape,tuple(cat for group in groups for cat in group),
            candidate_observations=1))
        self._segmented_index.add(
            tuple("\x1f".join(group) for group in groups),key)
        self.plans.append(compile_plan(
            shape,self.index.rules,token_groups=groups))
        return key

    @staticmethod
    def _lexical_slots(lattice):
        tokens=tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".","!","?"):
            tokens=tokens[:-1]
        at={(t.start,t.end):i for i,t in enumerate(tokens)}
        options=[{} for _ in tokens]
        for c in lattice.candidates:
            k=at.get((c.span_start,c.span_end))
            if k is not None:
                options[k].setdefault(c.category,[]).append(c)
        for by_cat in options:
            for candidates in by_cat.values():
                candidates.sort(key=lambda c:c.score,reverse=True)
        return options

    @staticmethod
    def _feature_at(candidate, path):
        value=candidate.features
        for feature in path:
            if not isinstance(value, FeatureStructure):
                return None
            value=value.features.get(feature)
        return value

    @staticmethod
    def _fill(plan, options, *, max_candidates_per_slot=None):
        """Backtrack lexical readings; intersect atom/disjunction domains.

        Preserve lexical alternatives and unresolved constraints instead of
        rejecting a valid vector parse merely because WordNet supplied a
        disjunction. No grammar rule reduction or ChartItem is instantiated.
        """
        if len(plan.slots)!=len(options):
            return None
        stack=[]
        bindings={group:frozenset((atom,)) for group,atom in plan.constants}
        selected=[None]*len(plan.slots)
        position=0
        while True:
            if position==len(plan.slots):
                return tuple(selected),tuple(sorted(
                    (group,next(iter(values)) if len(values)==1
                     else tuple(sorted(values)))
                    for group,values in bindings.items()))
            slot=plan.slots[position]
            candidate_options=options[position].get(slot.category,())
            if max_candidates_per_slot is not None:
                candidate_options=candidate_options[:max_candidates_per_slot]
            next_option=0
            if stack and stack[-1][0]==position:
                _,next_option,bindings=stack.pop()
            found=False
            for j in range(next_option,len(candidate_options)):
                candidate=candidate_options[j]
                trial=dict(bindings)
                if any(feature not in candidate.features.features or
                       isinstance(candidate.features.features[feature],Variable)
                       for feature in slot.requires):
                    continue
                valid=True
                for path,group in slot.checks:
                    value=CompiledStructureReplayer._feature_at(candidate,path)
                    if value is None or value is TOP or isinstance(value,Variable):
                        continue
                    if isinstance(value, Atom):
                        allowed=frozenset((value.symbol,))
                    elif isinstance(value,Disjunction):
                        # An unbound option imposes no lexical restriction.
                        if any(v is TOP or isinstance(v,Variable) for v in value.options):
                            continue
                        if not all(isinstance(v,Atom) for v in value.options):
                            valid=False
                            break
                        allowed=frozenset(v.symbol for v in value.options)
                    else:
                        valid=False
                        break
                    known=trial.get(group)
                    intersection=allowed if known is None else known & allowed
                    if not intersection:
                        valid=False
                        break
                    trial[group]=intersection
                if not valid:
                    continue
                stack.append((position,j+1,bindings))
                selected[position]=candidate
                bindings=trial
                position+=1
                found=True
                break
            if found:
                continue
            if not stack:
                return None
            position,_,_=stack[-1]

    @staticmethod
    def _token_segmentations(lattice):
        """Generate lexical paths through one token, not text cache keys.

        One token can be a grammatical path (V,NEG) or (N,POSS).
        Every lexical alternative is preserved at each span. Distinct
        contraction spellings can therefore share the same structure.
        """
        tokens=tuple(lattice.tokens)
        while tokens and tokens[-1].text in (".","!","?"):
            tokens=tokens[:-1]
        all_edges=[defaultdict(list) for _ in tokens]
        for cand in lattice.candidates:
            for i,tok in enumerate(tokens):
                if (tok.start<=cand.span_start<cand.span_end<=tok.end):
                    all_edges[i][(cand.span_start,cand.span_end,
                                  cand.category)].append(cand)
                    break
        paths=[]
        for tok,edges in zip(tokens,all_edges):
            by_start=defaultdict(list)
            for (start,end,cat),variants in edges.items():
                variants.sort(key=lambda c:c.score,reverse=True)
                by_start[start].append((end,cat,variants))
            groups=defaultdict(list)
            def visit(cursor,parts):
                if cursor==tok.end:
                    key="\x1f".join(p[0] for p in parts)
                    groups[key].append(tuple(parts))
                    return
                if len(parts)>=6:
                    return
                for end,cat,variants in by_start.get(cursor,()):
                    visit(end,parts+((cat,variants),))
            visit(tok.start,())
            paths.append(groups)
        return paths

    def _replay_segmented(self,lattice,*,page_size,max_candidates_per_slot):
        if not self._segmented_by_signature:
            return CompiledReplay(None,0,0,False,"unseen_pattern")
        paths=self._token_segmentations(lattice)
        choices=tuple(tuple(by_key) for by_key in paths)
        checked=0
        offset=0
        while True:
            found=self._segmented_index.lookup(
                choices,limit=page_size,offset=offset)
            for tid in found.template_ids:
                checked+=1
                plan=self.plans[tid]
                if plan is None:
                    continue
                keys=tuple("\x1f".join(group) for group in plan.token_category_groups)
                group_choices=[paths[i].get(key,()) for i,key in enumerate(keys)]
                if any(not group for group in group_choices):
                    continue
                # Separate lexical edge/segmentation choices, never splice
                # incompatible half-contraction candidates.
                for choice in product(*group_choices):
                    options=[]
                    for segments in choice:
                        options.extend({cat:variants} for cat,variants in segments)
                    filled=self._fill(
                        plan,options,
                        max_candidates_per_slot=max_candidates_per_slot)
                    if filled is None:
                        continue
                    selected,bindings=filled
                    occurrence=CompiledOccurrence(
                        tid,plan.structure,lattice.text,tuple(lattice.tokens),
                        selected,tuple(tuple(by_cat.get(slot.category,()))
                            for by_cat,slot in zip(options,plan.slots)),
                        plan,bindings)
                    return CompiledReplay(
                        occurrence,found.total,checked,
                        found.next_offset is not None,"matched")
            if found.next_offset is None:
                return CompiledReplay(
                    None,found.total,checked,False,
                    "unseen_pattern" if not found.total else "requires_fallback")
            offset=found.next_offset

    def replay(self,lattice,*,max_templates_checked=None,
               max_candidates_per_slot=None) -> CompiledReplay:
        """Page index candidates as needed. Never silently drop a learned ID.

        Candidate cap is optional; exhaustive is the default for the exact
        repeated-corpus experiment. Retrieval remains direct bitset lookup.
        """
        if max_templates_checked is not None and max_templates_checked<1:
            raise ValueError("Candidate budgets must be positive")
        if max_candidates_per_slot is not None and max_candidates_per_slot<1:
            raise ValueError("Candidate budgets must be positive")
        options=self._lexical_slots(lattice)
        signatures=tuple(tuple(by_cat) for by_cat in options)
        page_size=max_templates_checked or 128
        offset=0
        checked=0
        while True:
            result=self.index._positional_index.lookup(
                signatures,limit=page_size,offset=offset)
            for tid in result.template_ids:
                checked+=1
                plan=self.plans[tid]
                if plan is None:
                    continue
                filled=self._fill(plan,options,
                                  max_candidates_per_slot=max_candidates_per_slot)
                if filled is None:
                    continue
                selected,bindings=filled
                occurrence=CompiledOccurrence(
                    tid,plan.structure,lattice.text,tuple(lattice.tokens),
                    selected,tuple(tuple(by_cat.get(slot.category,()))
                        for by_cat,slot in zip(options,plan.slots)),
                    plan,bindings)
                return CompiledReplay(occurrence,result.total,
                                      checked,result.next_offset is not None,"matched")
            if result.next_offset is None:
                break
            offset=result.next_offset
        segmented=self._replay_segmented(
            lattice,page_size=page_size,
            max_candidates_per_slot=max_candidates_per_slot)
        if segmented.complete:
            return segmented
        return CompiledReplay(
            None,result.total+segmented.candidate_templates,
            checked+segmented.checked_templates,False,
            "unseen_pattern" if not result.total and
                not segmented.candidate_templates else "requires_fallback")
