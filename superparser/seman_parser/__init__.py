"""seman_parser — symbolic linguistic engine inspired by TRIPS.

Knowledge is data. The runtime provides generic operations
(INDEX, MATCH, UNIFY, EXPAND, PACK, SCORE, COMPOSE, LINK) and never
dispatches on linguistic content.
"""

from __future__ import annotations

from .chart import Chart, ChartItem, ParseResult, PackedNode, Provenance
from .engine import Parser, ParserResources, ParseReport
from .features import (
    Atom,
    Disjunction,
    FeatureStructure,
    UnificationFailure,
    Variable,
    substitute_structure,
    unify,
)
from .grammar import Grammar, GrammarRule, RuleSymbol, load_grammar
from .lexicon import (
    ArgumentSlot,
    LexicalEntry,
    LexicalSense,
    Lexicon,
    SenseFrame,
    load_lexicon,
)
from .segmentation import LexicalCandidate, LexicalLattice, build_lattice, tokenize
from .symbols import SymbolTable
from .syntax import SyntacticLink, SyntacticPackage

__all__ = [
    "ArgumentSlot",
    "Atom",
    "Chart",
    "ChartItem",
    "Disjunction",
    "FeatureStructure",
    "Grammar",
    "GrammarRule",
    "LexicalCandidate",
    "LexicalEntry",
    "LexicalLattice",
    "LexicalSense",
    "Lexicon",
    "ParseReport",
    "ParseResult",
    "PackedNode",
    "Parser",
    "ParserResources",
    "Provenance",
    "RuleSymbol",
    "SemanticAction",
    "SemanticGraph",
    "SemanticNode",
    "SemanticPackage",
    "SemanticRelation",
    "SyntacticLink",
    "SyntacticPackage",
    "SenseFrame",
    "SymbolTable",
    "TypeHierarchy",
    "UnificationFailure",
    "Variable",
    "build_lattice",
    "load_grammar",
    "load_lexicon",
    "load_types",
    "substitute_structure",
    "tokenize",
    "unify",
]

__version__ = "0.1.0"


_LAZY_EXPORTS = {
    "SemanticAction": ("semantic_rules", "SemanticAction"),
    "SemanticGraph": ("semantics", "SemanticGraph"),
    "SemanticNode": ("semantics", "SemanticNode"),
    "SemanticPackage": ("semantics", "SemanticPackage"),
    "SemanticRelation": ("semantics", "SemanticRelation"),
    "TypeHierarchy": ("types", "TypeHierarchy"),
    "load_types": ("types", "load_types"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    from importlib import import_module

    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
