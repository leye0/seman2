"""POC-06 tests restricted to the 849 cached real observations."""

from collections import defaultdict
from pathlib import Path

import pytest

from research.induction import LatentReferentModel
from research.induction.corpus_evidence import load_real_corpus, referent_substitution_observations


CACHE = Path(__file__).resolve().parents[2] / ".local/cache/seman2/induction"


@pytest.fixture(scope="module")
def real_model():
    graphs = load_real_corpus(CACHE, required=849)
    train = referent_substitution_observations(graphs[:600])
    validation = referent_substitution_observations(graphs[600:725], offset=600)
    test = referent_substitution_observations(graphs[725:], offset=725)
    model = LatentReferentModel(
        context_similarity=0.1,
        membership_ratio=0.75,
        min_contexts=2,
        min_referents=2,
    ).fit(train)
    return graphs, train, validation, test, model


def score(model, rows):
    actual = defaultdict(set)
    for row in rows:
        actual[row.context].add(row.referent_id)
    known = set(model.signatures)
    true_positive = predicted = gold = covered = 0
    for context, referents in actual.items():
        referents &= known
        if not referents:
            continue
        result = model.predict(context.component_id, context.port_id)
        if result.abstained:
            continue
        covered += 1
        proposed = set(result.referent_ids)
        true_positive += len(proposed & referents)
        predicted += len(proposed)
        gold += len(referents)
    precision = true_positive / predicted
    recall = true_positive / gold
    f1 = 2 * precision * recall / (precision + recall)
    noun_precision = gold / (len(known) * covered)
    noun_f1 = 2 * noun_precision / (noun_precision + 1)
    return covered, f1, noun_f1


def test_real_split_and_evidence_counts(real_model):
    graphs, train, validation, test, _ = real_model
    assert len(graphs) == 849
    assert (len(train), len(validation), len(test)) == (2756, 623, 591)


def test_real_training_discovers_five_families(real_model):
    *_, model = real_model
    assert len(model.families) == 5
    assert all(family.members for family in model.families)


def test_real_heldout_score_beats_real_noun_baseline(real_model):
    _, _, _, test, model = real_model
    covered, f1, noun_f1 = score(model, test)
    assert covered == 10
    assert f1 == pytest.approx(0.3064182194616977)
    assert f1 > noun_f1


def test_every_learned_member_is_attested_in_real_training(real_model):
    _, train, _, _, model = real_model
    attested = {row.referent_id for row in train}
    assert all(set(family.members) <= attested for family in model.families)
