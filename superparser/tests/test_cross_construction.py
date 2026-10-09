"""POC-11 controlled tests for transfer between constructions."""

from research.induction import (
    ConstructionEvidence,
    CrossConstructionLearner,
    EffectTemplate,
    ReportedProposition,
)


ACTIVE = (EffectTemplate("r", (0, 2), False), EffectTemplate("r", (1, 2), True))
PASSIVE = (EffectTemplate("r", (2, 0), False), EffectTemplate("r", (1, 0), True))


def occurrences(name, effects, count=6, residual=None):
    return [ConstructionEvidence.build(f"{name}-{i}", name, 3, effects, residual) for i in range(count)]


def test_discovers_argument_permutation_from_effects():
    learner = CrossConstructionLearner(min_support=4).fit(
        occurrences("active", ACTIVE) + occurrences("passive", PASSIVE)
    )
    assert learner.alignments
    alignment = learner.alignments[0]
    assert alignment.left_to_right == (2, 1, 0)
    assert set(alignment.predict_right(("item", "recipient", "giver"))) == {
        ReportedProposition("r", ("giver", "item"), False),
        ReportedProposition("r", ("recipient", "item"), True),
    }


def test_surface_residuals_are_preserved_not_erased():
    learner = CrossConstructionLearner().fit(
        occurrences("active", ACTIVE, residual={"voice": "active"})
        + occurrences("passive", PASSIVE, residual={"voice": "passive"})
    )
    alignment = learner.alignments[0]
    assert '"active"' in alignment.left_residuals[0]
    assert '"passive"' in alignment.right_residuals[0]


def test_opposite_polarity_is_not_a_paraphrase():
    opposite = (EffectTemplate("r", (2, 0), True), EffectTemplate("r", (1, 0), True))
    learner = CrossConstructionLearner().fit(occurrences("a", ACTIVE) + occurrences("b", opposite))
    assert learner.alignments == ()


def test_lexical_or_syntactic_similarity_without_effects_is_insufficient():
    rows = occurrences("same-looking-a", (), 6) + occurrences("same-looking-b", (), 6)
    assert CrossConstructionLearner().fit(rows).alignments == ()


def test_unused_ports_are_canonicalized_instead_of_permuted():
    effects = (EffectTemplate("r", (0,), True),)
    learner = CrossConstructionLearner().fit(occurrences("a", effects) + occurrences("b", effects))
    assert len(learner.alignments) == 1
    assert learner.alignments[0].left_to_right == (0, -1, -1)
