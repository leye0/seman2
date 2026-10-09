"""POC-09 tests for opaque transition induction."""

from research.induction import (
    EventOccurrence,
    PartialState,
    ReportedProposition,
    TransitionEpisode,
    TransitionInducer,
)


def prop(relation, *arguments, truth=True):
    return ReportedProposition(relation, tuple(arguments), truth)


def episode(index, component="e-transfer", *, effect=True, polarity=True, mode="asserted", outsider=False):
    a, b, item = f"a{index}", f"b{index}", f"o{index}"
    before = PartialState.build(f"before-{index}", "n", 0, [prop("r-has", a, item)])
    after_rows = []
    if effect:
        after_rows = [prop("r-has", a, item, truth=False), prop("r-has", b, item)]
    if outsider:
        after_rows.append(prop("r-noise", "unlinked", item))
    after = PartialState.build(f"after-{index}", "n", 2, after_rows)
    event = EventOccurrence(f"event-{index}", component, (a, b, item), "n", 1, polarity, mode)
    return TransitionEpisode(f"episode-{index}-{component}", "ctx", before, event, after)


def trained():
    rows = [episode(index) for index in range(10)]
    rows += [episode(100 + index, component="e-observe", effect=False) for index in range(10)]
    return TransitionInducer(min_support=5, min_lift=1.5).fit(rows)


def test_learns_argument_linked_effects_and_predicts_novel_referents():
    model = trained()
    event = EventOccurrence("held", "e-transfer", ("new-a", "new-b", "new-o"), "n", 1)
    predictions = model.predict(event, "ctx")
    propositions = {row.proposition for row in predictions}
    assert prop("r-has", "new-a", "new-o", truth=False) in propositions
    assert prop("r-has", "new-b", "new-o") in propositions
    assert all(row.explanation_chain[-1] == "held" for row in predictions)


def test_independent_event_abstains():
    model = trained()
    event = EventOccurrence("held", "e-observe", ("x", "y", "z"), "n", 1)
    assert model.predict(event, "ctx") == ()


def test_negated_and_hypothetical_events_neither_train_nor_predict():
    rows = [episode(index, polarity=False) for index in range(10)]
    rows += [episode(100 + index, mode="hypothetical") for index in range(10)]
    model = TransitionInducer(min_support=3).fit(rows)
    assert model.hypotheses == ()
    assert model.predict(rows[0].event, "ctx") == ()


def test_unlinked_referent_effect_is_not_generalized():
    rows = [episode(index, outsider=True) for index in range(10)]
    rows += [episode(100 + index, component="control", effect=False) for index in range(10)]
    model = TransitionInducer(min_support=5).fit(rows)
    assert all(hypothesis.effect.relation_id != "r-noise" for hypothesis in model.hypotheses)


def test_common_background_change_fails_lift_control():
    rows = [episode(index, component="event-a") for index in range(10)]
    rows += [episode(100 + index, component="event-b") for index in range(10)]
    model = TransitionInducer(min_support=5, min_lift=1.5).fit(rows)
    assert model.hypotheses == ()


def test_missing_effect_is_unknown_but_reduces_coverage():
    rows = [episode(index, effect=index < 8) for index in range(10)]
    rows += [episode(100 + index, component="control", effect=False) for index in range(10)]
    model = TransitionInducer(min_support=5, min_coverage=0.75).fit(rows)
    assert model.hypotheses
    assert all(hypothesis.contradictions == 0 for hypothesis in model.hypotheses)
    assert all(hypothesis.coverage == 0.8 for hypothesis in model.hypotheses)


def test_explicit_counterexamples_block_overgeneralization():
    rows = [episode(index) for index in range(8)]
    rows += [episode(100 + index, effect=False) for index in range(2)]
    # Make the two absences explicit opposite continuations.
    for offset in range(2):
        base = rows[8 + offset]
        a, b, item = base.event.arguments
        after = PartialState.build(f"counter-{offset}", "n", 2, [prop("r-has", b, item, truth=False)])
        rows[8 + offset] = TransitionEpisode(base.episode_id, base.context_id, base.before, base.event, after)
    rows += [episode(200 + index, component="control", effect=False) for index in range(10)]
    model = TransitionInducer(min_support=5, min_confidence=0.9).fit(rows)
    assert not any(
        hypothesis.effect.argument_slots == (1, 2) and hypothesis.effect.truth
        for hypothesis in model.hypotheses
    )
