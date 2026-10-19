"""Conservative grammar-feature replayer for observed subtree signatures.

A category-trie hit is NOT a parse. This module can establish a stronger
but still contextual claim: one COMPLETE rule-ID structure admits an actual
lexical-candidate assignment, under the same feature unifier, positive
requires evidence and sibling binding flow used by the Layer 1 materializer.

LIMIT: the witness does not establish a preferred or exhaustive parse, nor
compatibility under arbitrary parent context. Do NOT insert the witness into
the authoritative forest or remove other readings or semantic alternatives.
This module is an opt-in research probe only.

Signatures are compiled once per cache/grammar. Rule IDs, categories and
child arities must agree with CURRENT grammar; stale templates are refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from seman_parser.features import FeatureStructure, unify, substitute_structure
from seman_parser.symbols import intern
from seman_parser.vector_chart import _feature_evidence, _rule_evidence


@dataclass(frozen=True, slots=True)
class PreparedShape:
    category: str
    rule: Any | None
    children: tuple["PreparedShape", ...]
    leaf_count: int


@dataclass(frozen=True, slots=True)
class Assignment:
    features: FeatureStructure
    bindings: dict[str, Any]
    evidence: frozenset[int]
    candidates: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class FeatureReplay:
    status: str  # WITNESS | NO_WITNESS | BUDGET_UNKNOWN | UNSUPPORTED
    unification_attempts: int
    lexical_combinations: int
    witness_categories: tuple[str, ...] = ()


@dataclass(slots=True)
class _Counter:
    limit: int
    steps: int = 0
    leaves: int = 0
    exhausted: bool = False

    def step(self) -> bool:
        self.steps += 1
        if self.steps > self.limit:
            self.exhausted = True
            return False
        return True


class SubtreeFeatureReplayer:
    """Safe, capped check of a FIXED rule tree, not a substitute parser."""

    def __init__(self, templates, grammar) -> None:
        by_id: dict[str, Any] = {}
        ambiguous: set[str] = set()
        for rule in grammar:
            if rule.rule_id in by_id and rule != by_id[rule.rule_id]:
                ambiguous.add(rule.rule_id)
            by_id[rule.rule_id] = rule
        self.compiled: dict[int, PreparedShape] = {}
        self.unsupported: dict[int, str] = {}
        for index, template in enumerate(templates):
            try:
                compiled = self._compile(template.shape, by_id, ambiguous)
                if compiled.leaf_count != len(template.categories):
                    raise ValueError("Signature leaf arity changed")
                self.compiled[index] = compiled
            except (ValueError, TypeError) as exc:
                self.unsupported[index] = str(exc)

    @classmethod
    def _compile(cls, shape, by_id, ambiguous) -> PreparedShape:
        if not isinstance(shape, tuple) or not shape:
            raise ValueError("Invalid stored rule shape")
        if shape[0] == "lex":
            if len(shape) != 2 or not isinstance(shape[1], str):
                raise ValueError("Invalid lexical leaf")
            return PreparedShape(shape[1], None, (), 1)
        if shape[0] != "rule" or len(shape) != 4:
            raise ValueError("Invalid rule signature")
        _, rule_id, category, child_shapes = shape
        if rule_id in ambiguous or rule_id not in by_id:
            raise ValueError("Missing or ambiguous current grammar rule")
        rule = by_id[rule_id]
        if rule.lhs.category != category or len(rule.rhs) != len(child_shapes):
            raise ValueError("Changed LHS or rule arity")
        children = tuple(cls._compile(child, by_id, ambiguous)
                         for child in child_shapes)
        if any(sym.category != child.category
               for sym, child in zip(rule.rhs, children)):
            raise ValueError("Changed RHS lexical category")
        return PreparedShape(category, rule, children,
                             sum(child.leaf_count for child in children))

    def replay(self, hint, lattice, *, max_steps: int = 1000) -> FeatureReplay:
        if max_steps < 1:
            raise ValueError("A positive replay work budget is required")
        root = self.compiled.get(hint.template_id)
        if root is None:
            return FeatureReplay("UNSUPPORTED", 0, 0)
        if hint.end_token-hint.start_token != root.leaf_count:
            return FeatureReplay("UNSUPPORTED", 0, 0)
        if not 0 <= hint.start_token < hint.end_token <= len(lattice.tokens):
            return FeatureReplay("UNSUPPORTED", 0, 0)
        tokens=lattice.tokens
        if (hint.start_char != tokens[hint.start_token].start
            or hint.end_char != tokens[hint.end_token-1].end
            or hint.root_category != root.category
            or root.rule is None
            or hint.root_rule != root.rule.rule_id):
            return FeatureReplay("UNSUPPORTED", 0, 0)
        options: dict[tuple[int,int], list[Any]]={}
        for candidate in lattice.candidates:
            options.setdefault((candidate.span_start,candidate.span_end),[]
                               ).append(candidate)
        count=_Counter(max_steps)

        def walk(node: PreparedShape, offset: int, constraint: FeatureStructure,
                 env: dict[str,Any], requires: tuple[str,...]):
            if count.exhausted:
                return
            if node.rule is None:
                token=tokens[offset]
                for cand in options.get((token.start,token.end),()):
                    if count.exhausted:
                        return
                    if cand.category != node.category or cand.interface is not None:
                        continue
                    if not count.step():
                        return
                    count.leaves += 1
                    evidence = _feature_evidence(cand.features)
                    if not all(intern(name) in evidence for name in requires):
                        continue
                    matched=unify(constraint,cand.features,env)
                    if matched is not None:
                        features, bindings=matched
                        yield Assignment(features,bindings,evidence,(cand,))
                return
            if not count.step():
                return
            lhs=unify(constraint,node.rule.lhs.features,env)
            if lhs is None:
                return
            lhs_features,initial_env=lhs

            def visit_child(i:int,at:int,bindings:dict[str,Any],
                            matched:list[Assignment], candidates:tuple[Any,...]):
                if count.exhausted:
                    return
                if i==len(node.children):
                    evidence = _rule_evidence(node.rule,matched)
                    if all(intern(name) in evidence for name in requires):
                        yield Assignment(substitute_structure(lhs_features,bindings),
                                         dict(bindings),evidence,candidates)
                    return
                child=node.children[i]
                sym=node.rule.rhs[i]
                for result in walk(child,at,sym.features,bindings,sym.requires):
                    yield from visit_child(i+1,at+child.leaf_count,
                                           result.bindings,matched+[result],
                                           candidates+result.candidates)
                    if count.exhausted:
                        return

            yield from visit_child(0,offset,initial_env,[],())

        for witness in walk(root,hint.start_token,FeatureStructure.empty(),{},()):
            return FeatureReplay("WITNESS", count.steps, count.leaves,
                                 tuple(c.category for c in witness.candidates))
        return FeatureReplay("BUDGET_UNKNOWN" if count.exhausted
                             else "NO_WITNESS", count.steps,count.leaves)
