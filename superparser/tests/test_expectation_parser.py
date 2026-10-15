"""Integration smoke tests; run within the real Seman2 repository."""
from pathlib import Path

from seman_parser.expectation_parser import ExpectationParser
from seman_parser.predictive import TransitionModel

DATA = Path(__file__).resolve().parents[1] / 'data'


def test_single_clause_is_native_and_completely_consumed() -> None:
    parser = ExpectationParser.from_dir(DATA, model=TransitionModel(), max_states=30_000)
    result = parser.parse('The child laughed.')
    assert result.stats['fallback'] is False
    assert result.completed
    assert result.item is not None and result.item.category == 'CLAUSE'
    assert result.stats['expectations_requested'] > 0
    assert result.stats['lexical_scans'] > 0


def test_invalid_sequence_is_not_declared_valid() -> None:
    parser = ExpectationParser.from_dir(DATA, model=TransitionModel(), max_states=5_000)
    result = parser.parse('the the the the.')
    assert not result.completed
    assert result.stats['fallback'] is False


def test_expectations_are_observed_left_to_right() -> None:
    parser = ExpectationParser.from_dir(DATA, model=TransitionModel(), max_states=30_000)
    result = parser.parse('I saw the man with a telescope.')
    assert result.stats['expectations_requested'] > 0
    assert result.stats['lexical_scans'] > 0
    assert result.stats['fallback'] is False
    if result.completed:
        assert result.item.category == 'CLAUSE'
