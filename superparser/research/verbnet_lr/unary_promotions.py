"""Research-only lexical-head promotion inference for existing phrase categories.

No sentence, lemma, surface form or corpus ID appears in these rules.
A phrase category ending in 'P' (NP, VP, ADJP, ADVP) is eligible only
when its remainder is an observed lexical category (N, V, ADJ, ADV),
the grammar already uses that phrase nonterminal and *lacks* a direct
unary rule. This intentionally yields ADVP -> ADV for the current grammar.

The rule is an explicit, inspectable hypothesis and MUST be evaluated on
independent positive/negative grammar tests. Never writes grammar.jsonl.
"""
from __future__ import annotations

from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol


def propose_unary_head_promotions(grammar: Grammar) -> tuple[GrammarRule, ...]:
    rules = tuple(grammar.rules)
    lhs_categories = {r.lhs.category for r in rules}
    all_rhs = {s.category for r in rules for s in r.rhs}
    lexical = all_rhs - lhs_categories
    signatures = {
        (r.lhs.category, tuple(s.category for s in r.rhs)) for r in rules
    }
    inferred = []
    for phrase in sorted(lhs_categories):
        if not phrase.endswith("P"):
            continue
        head = phrase[:-1]
        if head not in lexical or (phrase, (head,)) in signatures:
            continue
        inferred.append(
            GrammarRule(
                rule_id=f"research_unary_{phrase.lower()}_{head.lower()}",
                rhs=(RuleSymbol(head),),
                lhs=RuleSymbol(phrase),
                score=0.8,
                provenance={"source": "experimental_unary_head_promotion",
                            "mechanism": "phrase_suffix_P",
                            "requires_validation": True},
            )
        )
    return tuple(inferred)


def with_unary_head_promotions(grammar: Grammar) -> tuple[Grammar, tuple[GrammarRule, ...]]:
    suggestions = propose_unary_head_promotions(grammar)
    return Grammar((*grammar.rules, *suggestions)), suggestions
