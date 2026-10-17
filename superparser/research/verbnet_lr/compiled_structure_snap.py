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
from typing import Any

from seman_parser.features import Atom, Variable, TOP
from seman_parser.symbols import intern
from .full_structure_snap import FullStructureSnapIndex, Structure


@dataclass(frozen=True, slots=True)
class CompiledSlot:
    category: str
    checks: tuple[tuple[int, int], ...]  # (feature ID, precompiled equality group)
    requires: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompiledPlan:
    structure: Structure  # immutable and SHARED, never cloned at replay
    slots: tuple[CompiledSlot, ...]
    constants: tuple[tuple[int, int], ...]  # (group, interned atom)
    rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledOccurrence:
    """Ready for a future Layer 2 adapter; NOT a ChartItem/ParseResult."""
    structure_id: int
    structure: Structure
    original_text: str
    tokens: tuple[Any, ...]
    lexical_slots: tuple[Any, ...]
    plan: CompiledPlan
    feature_bindings: tuple[tuple[int, int], ...]

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


def compile_plan(shape: Structure, rules: dict[str, Any]) -> CompiledPlan | None:
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

    def attach(node_id, features, rule_instance):
        nonlocal unsupported
        for attr, value in features.items():
            key = ("node", node_id, attr)
            union.root(key)
            if isinstance(value, Atom):
                union.constant(key, value.symbol)
            elif isinstance(value, Variable):
                union.join(key, ("var", rule_instance, value.name))
            elif value is TOP:
                continue
            else:
                # Nested structures/disjunctions need a separate fast-path
                # compiler; never silently drop constraints.
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
    return CompiledPlan(shape,slots,constants,tuple(rule_ids))


class CompiledStructureReplayer:
    """Structure learning then direct indexed replay, returning a word overlay."""

    def __init__(self, resources, *, max_templates=20_000_000):
        self.index = FullStructureSnapIndex(resources,max_templates=max_templates)
        self.plans: list[CompiledPlan | None] = []

    def observe(self, item, *, lattice, evidence="candidate") -> int:
        key=self.index.observe(item,lattice=lattice,evidence=evidence)
        if key==len(self.plans):
            template=self.index.templates[key]
            self.plans.append(compile_plan(template.shape,self.index.rules))
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
    def _fill(plan, options, *, max_candidates_per_slot):
        if len(plan.slots)!=len(options):
            return None
        bindings=dict(plan.constants)
        chosen=[]
        for slot,by_cat in zip(plan.slots,options):
            candidates=by_cat.get(slot.category,())
            matched=None
            for candidate in candidates[:max_candidates_per_slot]:
                # Clone only the tiny feature-value environment, never an
                # existing grammatical tree.
                trial=dict(bindings)
                valid=True
                for feature in slot.requires:
                    value=candidate.features.features.get(feature)
                    if value is None or isinstance(value,Variable):
                        valid=False
                        break
                if not valid:
                    continue
                for feature,group in slot.checks:
                    value=candidate.features.features.get(feature)
                    if value is None or value is TOP:
                        continue
                    if not isinstance(value,Atom):
                        valid=False
                        break
                    known=trial.get(group)
                    if known is not None and known!=value.symbol:
                        valid=False
                        break
                    trial[group]=value.symbol
                if valid:
                    matched=candidate
                    bindings=trial
                    break
            if matched is None:
                return None
            chosen.append(matched)
        return tuple(chosen),tuple(sorted(bindings.items()))

    def replay(self,lattice,*,max_templates_checked=32,
               max_candidates_per_slot=8) -> CompiledReplay:
        if max_templates_checked<1 or max_candidates_per_slot<1:
            raise ValueError("Candidate budgets must be positive")
        options=self._lexical_slots(lattice)
        result=self.index._positional_index.lookup(
            tuple(tuple(by_cat) for by_cat in options),
            limit=max_templates_checked)
        for tid in result.template_ids:
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
                selected,plan,bindings)
            return CompiledReplay(occurrence,result.total,
                                  len(result.template_ids),
                                  result.next_offset is not None,"matched")
        return CompiledReplay(
            None,result.total,len(result.template_ids),
            result.next_offset is not None,
            "unseen_pattern" if not result.total else "requires_fallback")
