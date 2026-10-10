from pathlib import Path

from grammar_induction_sweep import _resources_without, mask_families
from research.induction.masked_grammar_induction import (
    CandidateKey,
    SweepConfig,
    aggregate_observations,
    parser_with_candidates,
    rank_candidates,
)
from seman_parser import Parser, ParserResources


DATA = Path(__file__).resolve().parents[1] / "data"


def test_coordination_is_rediscovered_without_hidden_rule_oracle():
    resources = ParserResources.from_dir(DATA)
    hidden = mask_families(resources.grammar)["np_coordination"]
    masked = _resources_without(resources, hidden)
    parser = Parser(masked, cache_size=0)
    training = (
        "The boy and the girl laughed.",
        "The cat and the dog slept.",
        "The mother and the father worked.",
    )
    observations = [
        (f"train-{index}", parser.parse(text).result)
        for index, text in enumerate(training)
    ]

    evidence = aggregate_observations(
        observations, max_pattern=3, method="bridge", generalization_depth=2,
    )
    candidates = rank_candidates(
        evidence,
        masked.grammar,
        SweepConfig("bridge", 3, 2, "none", 8, 2),
    )

    assert CandidateKey("NP", ("NP", "COORD", "NP")) in {
        row.key for row in candidates
    }
    learned = parser_with_candidates(masked, candidates, feature_mode="none")
    result = learned.parse("The teacher and the student talked.").result
    assert result.completed
    induced_ids = {
        forest.compiled.rules[derivation.rule_index].rule.rule_id
        for forest in (result.shared_forest,)
        for node in forest.nodes
        for derivation in node.derivations
        if getattr(derivation, "rule_index", None) is not None
        and forest.compiled.rules[derivation.rule_index].rule.rule_id.startswith("induced_")
    }
    assert induced_ids


def test_mask_closes_duplicate_rule_shapes():
    resources = ParserResources.from_dir(DATA)
    families = mask_families(resources.grammar)
    pp_signatures = {
        (rule.lhs.category, tuple(symbol.category for symbol in rule.rhs))
        for rule in resources.grammar
        if rule.rule_id in families["nominal_pp_attachment"]
    }
    assert ("NP", ("NP", "PP")) in pp_signatures
    masked = _resources_without(resources, families["nominal_pp_attachment"])
    assert not any(
        rule.lhs.category == "NP"
        and tuple(symbol.category for symbol in rule.rhs) == ("NP", "PP")
        for rule in masked.grammar
    )
