"""POC-08 tests restricted to real consecutive partial states."""

from pathlib import Path

import pytest

from research.induction import compare_partial_states
from research.induction.corpus_evidence import load_real_corpus, reference_partial_states


CACHE = Path(__file__).resolve().parents[2] / ".local/cache/seman2/induction"


@pytest.fixture(scope="module")
def real_deltas():
    graphs = load_real_corpus(CACHE, required=849)
    states = reference_partial_states(graphs)
    deltas = [compare_partial_states(left, right) for left, right in zip(states, states[1:])]
    return graphs, states, deltas


def test_all_real_consecutive_states_are_compared(real_deltas):
    graphs, states, deltas = real_deltas
    assert len(graphs) == len(states) == 849
    assert len(deltas) == 848
    assert all(delta.comparable for delta in deltas)


def test_real_unmentioned_facts_are_never_encoded_as_reversals(real_deltas):
    _, _, deltas = real_deltas
    unmentioned = sum(len(delta.unmentioned_after) for delta in deltas)
    reversed_rows = sum(len(delta.explicitly_reversed) for delta in deltas)
    overlap = sum(
        len(set(delta.unmentioned_after) & {before for before, _ in delta.explicitly_reversed})
        for delta in deltas
    )
    assert unmentioned == 3029
    assert reversed_rows == 0
    assert overlap == 0


def test_real_delta_counts_are_stable(real_deltas):
    _, _, deltas = real_deltas
    assert sum(len(delta.added) for delta in deltas) == 3030
    assert sum(len(delta.unchanged) for delta in deltas) == 0


def test_real_states_have_monotonic_time_and_single_source(real_deltas):
    _, states, _ = real_deltas
    assert {state.source_id for state in states} == {"narrative-source"}
    assert [state.time_index for state in states] == list(range(849))
