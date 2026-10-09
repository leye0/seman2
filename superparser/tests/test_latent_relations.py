"""POC-07 tests restricted to real reference constraints."""

from pathlib import Path

import pytest

from research.induction import LatentRelationModel
from research.induction.corpus_evidence import load_real_corpus, reference_relation_observations


CACHE = Path(__file__).resolve().parents[2] / ".local/cache/seman2/induction"


@pytest.fixture(scope="module")
def real_relations():
    graphs = load_real_corpus(CACHE, required=849)
    train = reference_relation_observations(graphs[:600])
    test = reference_relation_observations(graphs[725:], offset=725)
    model = LatentRelationModel(
        min_support=3,
        min_confidence=0.9,
        min_coverage=0.2,
        min_calibrated_confidence=0.2,
    ).fit(train)
    return graphs, train, test, model


def test_real_constraint_counts(real_relations):
    graphs, train, test, _ = real_relations
    assert len(graphs) == 849
    assert (len(train), len(test)) == (2129, 428)


def test_only_attested_real_hypothesis_is_retained(real_relations):
    *_, model = real_relations
    assert len(model.hypotheses) == 1
    hypothesis = model.hypotheses[0]
    assert hypothesis.kind == "INCOMPATIBLE"
    assert hypothesis.support == 5
    assert hypothesis.contradictions == 0
    assert hypothesis.coverage == pytest.approx(5 / 6)


def test_real_heldout_produces_no_unsupported_prediction(real_relations):
    _, _, test, model = real_relations
    predictions = {
        prediction
        for row in test
        if row.truth
        for prediction in model.predict(row)
    }
    assert predictions == set()


def test_real_result_remains_predictive_no_go(real_relations):
    _, _, test, model = real_relations
    prediction_count = sum(len(model.predict(row)) for row in test if row.truth)
    assert prediction_count < 1
