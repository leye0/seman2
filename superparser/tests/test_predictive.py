"""Contract tests for the isolated predictive-parser POC."""

from __future__ import annotations

from pathlib import Path

from seman_parser.chart import ChartItem
from seman_parser.predictive import (
    HybridPredictiveParser,
    PredictiveGrammar,
    PredictiveParser,
    SharedPredictiveParser,
    TransitionModel,
)


DATA = Path(__file__).resolve().parents[1] / "data"


def _rules(item: ChartItem) -> tuple[object, ...]:
    return (item.rule_id, tuple(_rules(child) for child in item.children))


def test_compiler_indexes_real_grammar_and_reports_lr_feasibility() -> None:
    parser = PredictiveParser.from_dir(DATA)
    report = PredictiveGrammar(parser.resources.grammar, measure_lr0=True).report
    assert report.rules == 385
    assert report.lr0_states > 500
    assert report.lr0_conflict_states > 300
    assert report.left_recursive_rules > 50
    assert report.compiled_bytes_estimate > 0


def test_transition_model_round_trip(tmp_path: Path) -> None:
    model = TransitionModel(alpha=3.0)
    model.observe(["NP"], "V", "reduce:example", weight=2.0)
    path = tmp_path / "model.json"
    model.save(path)
    restored = TransitionModel.load(path)
    assert restored.alpha == 3.0
    assert restored.probability(["NP"], "V", "reduce:example") > restored.probability(
        ["NP"], "V", "reduce:other"
    )


def test_trained_fast_parse_is_native_and_feature_checked() -> None:
    parser = PredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
    )
    result = parser.parse("John opened the box.")
    assert result.completed
    assert result.item is not None and result.item.category == "CLAUSE"
    assert result.stats["fallback"] is False
    assert result.stats["feature_rejections"] > 0


def test_impossible_function_word_sequence_fails_honestly() -> None:
    parser = PredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
        max_states=2_000,
    )
    result = parser.parse("the the the the.")
    assert not result.completed
    assert result.stats["fallback"] is False


def test_expand_reuses_checkpoint_and_recovers_pp_attachment() -> None:
    parser = PredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
    )
    fast = parser.parse("I saw the man with a telescope.")
    assert fast.completed and fast.item is not None
    checkpoint = next(
        point for point in fast.ambiguities
        if point.selected_action == "shift:PREP" and "reduce:vp_transitive" in point.alternatives
    )
    expanded = parser.expand(fast, checkpoint.ambiguity_id)
    assert expanded.completed and expanded.item is not None
    assert _rules(expanded.item) != _rules(fast.item)
    assert expanded.stats["lexical_ms"] < 0.1
    assert expanded.stats["states_visited"] < 500


def test_shared_packing_propagates_better_derivation() -> None:
    parser = SharedPredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
        max_states=20_000, lookahead=1,
    )
    result = parser.parse("Making mistakes teaches humility.")
    assert result.completed and result.item is not None
    assert result.item.children[0].rule_id == "np_gerund"
    assert result.stats["backtracks"] == 0
    assert result.stats["shared_nodes"] > 0


def test_hybrid_escalates_unlikely_open_class_homograph() -> None:
    parser = HybridPredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
        max_states=20_000, fast_states=64, lookahead=1,
    )
    result = parser.parse("Are the keys inside the box?")
    assert result.completed and result.item is not None
    assert result.stats["shared_escalation"] is True
    assert result.item.children[0].category == "COPULA"
    assert result.stats["fallback"] is False


def test_shared_expand_reuses_search_and_returns_an_alternative() -> None:
    parser = SharedPredictiveParser.from_dir(
        DATA, model=TransitionModel.load(DATA / "predictive_transitions.json"),
        max_states=20_000, lookahead=1,
    )
    fast = parser.parse("Are the keys inside the box?")
    expanded = parser.expand(fast, 0)
    assert fast.completed and expanded.completed
    assert expanded.stats["lexical_ms"] == 0.0
    assert _rules(expanded.item) != _rules(fast.item)
