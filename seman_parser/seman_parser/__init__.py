"""seman_parser — symbolic linguistic engine inspired by TRIPS.

Knowledge is data. The runtime provides generic operations
(INDEX, MATCH, UNIFY, EXPAND, PACK, SCORE, COMPOSE, LINK) and never
dispatches on linguistic content.
"""

from __future__ import annotations

from .chart import Chart, ChartItem, ParseResult, PackedNode, Provenance
from .coref import CoreferenceResolver, ResolverConfig, link_best
from .discourse import (
    CoreferenceHypothesis,
    DiscourseEntity,
    DiscourseState,
    Mention,
)
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
from .grammar import Grammar, GrammarRule, RuleSymbol, SemanticAction, load_grammar
from .lexicon import (
    ArgumentSlot,
    LexicalEntry,
    LexicalSense,
    Lexicon,
    SenseFrame,
    load_lexicon,
)
from .mentions import extract_mentions, mention_from_item
from .reader import DiscourseProcessor, DiscourseReport, SentenceAnalysis
from .segmentation import LexicalCandidate, LexicalLattice, build_lattice, tokenize
from .semantics import (
    SemanticGraph,
    SemanticNode,
    SemanticPackage,
    SemanticRelation,
)
from .symbols import SymbolTable
from .types import TypeHierarchy, load_types

__all__ = [
    "ArgumentSlot",
    "Atom",
    "Chart",
    "ChartItem",
    "CoreferenceHypothesis",
    "CoreferenceResolver",
    "Disjunction",
    "DiscourseEntity",
    "DiscourseProcessor",
    "DiscourseReport",
    "DiscourseState",
    "FeatureStructure",
    "Grammar",
    "GrammarRule",
    "LexicalCandidate",
    "LexicalEntry",
    "LexicalLattice",
    "LexicalSense",
    "Lexicon",
    "Mention",
    "ParseReport",
    "ParseResult",
    "PackedNode",
    "Parser",
    "ParserResources",
    "Provenance",
    "ResolverConfig",
    "RuleSymbol",
    "SemanticAction",
    "SemanticGraph",
    "SemanticNode",
    "SemanticPackage",
    "SemanticRelation",
    "SenseFrame",
    "SentenceAnalysis",
    "SymbolTable",
    "TypeHierarchy",
    "UnificationFailure",
    "Variable",
    "build_lattice",
    "extract_mentions",
    "link_best",
    "load_grammar",
    "load_lexicon",
    "load_types",
    "mention_from_item",
    "substitute_structure",
    "tokenize",
    "unify",
]

__version__ = "0.1.0"
