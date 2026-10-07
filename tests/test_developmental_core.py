from __future__ import annotations

import unittest

from seman2_runtime.developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    EpistemicState,
    EventOccurrence,
    FormFactor,
    IdentityAnchor,
    Polarity,
    RelationEffect,
    RelationEffectKind,
    RelationOccurrence,
    RelationalUniverse,
    RoleBinding,
    StateCondition,
    StateEffect,
    StateFacet,
    SituatedFacet,
    TransitionCandidate,
)


class RelationalUniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.universe = RelationalUniverse()
        self.universe.add_context(ContextFrame("ctx:now", ContextKind.CURRENT))

    def test_contexts_keep_attributed_content_out_of_current_world(self) -> None:
        self.universe.add_identity(
            IdentityAnchor("person:paul", "ctx:now", ("obs:paul",), ("Paul",))
        )
        self.universe.add_context(
            ContextFrame(
                "ctx:paul-belief",
                ContextKind.ATTRIBUTED,
                parent_context_ref="ctx:now",
                attribution_ref="person:paul",
                support_refs=("obs:said",),
            )
        )
        relation = RelationOccurrence(
            "rel:rain-belief",
            "weather:rain",
            (RoleBinding("location", "place:garden"),),
            "ctx:paul-belief",
            1,
            Polarity.POSITIVE,
            "asserted-by-source",
            "person:paul",
            ("obs:said",),
            (),
            EpistemicState.ATTRIBUTED,
        )
        self.universe.add_relation(relation)

        self.assertEqual(
            self.universe.query_relations(
                relation_form_ref="weather:rain", context_ref="ctx:now"
            ),
            (),
        )
        self.assertEqual(
            self.universe.query_relations(
                relation_form_ref="weather:rain", context_ref="ctx:paul-belief"
            ),
            (relation,),
        )

    def test_one_identity_can_have_separate_contextual_facets(self) -> None:
        identity = IdentityAnchor(
            "person:maya", "ctx:now", ("obs:maya",), ("Maya",)
        )
        self.universe.add_identity(identity)
        self.universe.add_context(
            ContextFrame("ctx:memory", ContextKind.NARRATED, "ctx:now")
        )
        current = SituatedFacet(
            "facet:maya-now",
            "person:maya",
            "ctx:now",
            active_role_refs=("role:agent",),
            distributed_form_ref="form:maya-now",
            support_refs=("obs:now",),
            temporal_start=2,
        )
        remembered = SituatedFacet(
            "facet:maya-memory",
            "person:maya",
            "ctx:memory",
            active_role_refs=("role:remembered-agent",),
            distributed_form_ref="form:maya-memory",
            support_refs=("episode:yesterday",),
            temporal_start=1,
            temporal_end=1,
        )
        self.universe.add_facet(current)
        self.universe.add_facet(remembered)

        self.assertEqual(self.universe.facets[current.facet_id].identity_ref, identity.identity_id)
        self.assertEqual(
            self.universe.facets[remembered.facet_id].identity_ref, identity.identity_id
        )
        self.assertNotEqual(current.context_ref, remembered.context_ref)
        self.assertNotEqual(current.active_role_refs, remembered.active_role_refs)

    def test_sequential_generic_transitions_preserve_state_history(self) -> None:
        self.universe.add_state(
            StateFacet(
                "state:lamp-off-0",
                "object:lamp",
                "dimension:power",
                "value:off",
                "ctx:now",
                0,
                ("obs:initial",),
                EpistemicState.OBSERVED,
            )
        )
        for event_id, event_form, at in (
            ("event:1", "event-form:a", 1),
            ("event:2", "event-form:b", 2),
        ):
            self.universe.add_event(
                EventOccurrence(
                    event_id,
                    event_form,
                    (RoleBinding("participant", "object:lamp"),),
                    "ctx:now",
                    at,
                    (f"obs:{at}",),
                )
            )
        first = TransitionCandidate(
            "transition:1",
            "event:1",
            preconditions=(
                StateCondition(
                    "object:lamp", "dimension:power", "value:off", "ctx:now"
                ),
            ),
            state_effects=(
                StateEffect(
                    "object:lamp", "dimension:power", "value:on", "ctx:now"
                ),
            ),
            support_occurrence_refs=("obs:1",),
        )
        second = TransitionCandidate(
            "transition:2",
            "event:2",
            preconditions=(
                StateCondition(
                    "object:lamp", "dimension:power", "value:on", "ctx:now"
                ),
            ),
            state_effects=(
                StateEffect(
                    "object:lamp", "dimension:power", "value:off", "ctx:now"
                ),
            ),
            support_occurrence_refs=("obs:2",),
        )
        self.universe.add_transition(first)
        self.universe.add_transition(second)
        preview = self.universe.replay_transition("transition:1")
        self.assertEqual(len(self.universe.states), 1)
        self.assertEqual(preview.closed_state_refs, ("state:lamp-off-0",))

        result_1 = self.universe.apply_transition("transition:1")
        self.assertEqual(
            self.universe.current_state(
                bearer_ref="object:lamp",
                dimension_ref="dimension:power",
                context_ref="ctx:now",
            ).value_refs,
            ("value:on",),
        )
        self.universe.apply_transition("transition:2")

        self.assertEqual(
            self.universe.current_state(
                bearer_ref="object:lamp",
                dimension_ref="dimension:power",
                context_ref="ctx:now",
            ).value_refs,
            ("value:off",),
        )
        self.assertEqual(
            self.universe.current_state(
                bearer_ref="object:lamp",
                dimension_ref="dimension:power",
                context_ref="ctx:now",
                at=1,
            ).value_refs,
            ("value:on",),
        )
        self.assertEqual(len(self.universe.states), 3)
        self.assertEqual(
            self.universe.states[result_1.opened_state_refs[0]].supersedes_state_ref,
            "state:lamp-off-0",
        )

    def test_relation_transfer_closes_old_binding_and_opens_new_one(self) -> None:
        initial = RelationOccurrence(
            "rel:custody-marie",
            "relation:custody",
            (
                RoleBinding("theme", "object:book"),
                RoleBinding("custodian", "person:marie"),
            ),
            "ctx:now",
            0,
            Polarity.POSITIVE,
            "actual",
            None,
            ("obs:initial",),
            (),
            EpistemicState.OBSERVED,
        )
        self.universe.add_relation(initial)
        self.universe.add_event(
            EventOccurrence(
                "event:transfer",
                "event-form:unlabelled-transfer",
                (
                    RoleBinding("theme", "object:book"),
                    RoleBinding("recipient", "person:luc"),
                ),
                "ctx:now",
                1,
                ("obs:transfer",),
            )
        )
        transition = TransitionCandidate(
            "transition:transfer",
            "event:transfer",
            relation_effects=(
                RelationEffect(
                    RelationEffectKind.CLOSE,
                    "relation:custody",
                    (RoleBinding("theme", "object:book"),),
                    "ctx:now",
                ),
                RelationEffect(
                    RelationEffectKind.OPEN,
                    "relation:custody",
                    (
                        RoleBinding("theme", "object:book"),
                        RoleBinding("custodian", "person:luc"),
                    ),
                    "ctx:now",
                ),
            ),
            support_occurrence_refs=("obs:transfer",),
        )
        self.universe.add_transition(transition)
        result = self.universe.apply_transition("transition:transfer")

        current = self.universe.query_relations(
            relation_form_ref="relation:custody",
            required_bindings=(RoleBinding("theme", "object:book"),),
            context_ref="ctx:now",
        )
        self.assertEqual(len(current), 1)
        self.assertIn(RoleBinding("custodian", "person:luc"), current[0].bindings)
        self.assertEqual(result.closed_relation_refs, ("rel:custody-marie",))
        historical = self.universe.query_relations(
            relation_form_ref="relation:custody",
            required_bindings=(RoleBinding("custodian", "person:marie"),),
            context_ref="ctx:now",
            at=0,
        )
        self.assertEqual(historical, (initial,))

    def test_missing_relation_and_state_report_absence_without_invention(self) -> None:
        state = self.universe.current_state(
            bearer_ref="object:unknown",
            dimension_ref="dimension:colour",
            context_ref="ctx:now",
        )
        self.assertEqual(state.status, "unknown")
        self.assertEqual(state.value_refs, ())
        self.assertEqual(
            self.universe.query_relations(
                relation_form_ref="relation:unknown", context_ref="ctx:now"
            ),
            (),
        )


class DistributedFormTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = DevelopmentalCore(vector_dimension=2048, seed="test-core")
        self.core.universe.add_context(ContextFrame("ctx:today", ContextKind.CURRENT))
        self.core.universe.add_context(ContextFrame("ctx:yesterday", ContextKind.NARRATED))

    def test_bind_superpose_decode_and_trace_are_synchronized(self) -> None:
        factors = (
            FormFactor("factor:event-kind", "concept:bite", "ctx:today", "kind", support_refs=("rel:1",)),
            FormFactor("factor:agent", "person:maya", "ctx:today", "agent", support_refs=("rel:2",)),
            FormFactor("factor:patient", "object:apple-2", "ctx:today", "patient", support_refs=("rel:3",)),
        )
        form = self.core.encode_form("form:event-2", factors)
        distractor = FormFactor(
            "factor:distractor", "object:stone", "ctx:today", "patient"
        )
        decoded = self.core.forms.decode(form, factors + (distractor,))

        traced = {row.factor_ref for row in decoded if row.traced}
        self.assertEqual(traced, {factor.factor_ref for factor in factors})
        self.assertEqual(len(self.core.explain_form("form:event-2")), 3)
        unbound = self.core.forms.unbind_role(
            form,
            "patient",
            ("object:apple-2", "object:stone", "person:maya"),
        )
        self.assertEqual(unbound[0][0], "object:apple-2")

    def test_contextual_forms_do_not_copy_old_property_to_new_object(self) -> None:
        yesterday = self.core.encode_form(
            "form:apple-yesterday",
            (
                FormFactor("old:identity", "object:apple-1", "ctx:yesterday", "identity"),
                FormFactor("old:colour", "value:green", "ctx:yesterday", "colour"),
                FormFactor("old:patient", "concept:bite", "ctx:yesterday", "participates-in"),
            ),
        )
        today = self.core.encode_form(
            "form:apple-today",
            (
                FormFactor("new:identity", "object:apple-2", "ctx:today", "identity"),
                FormFactor("new:patient", "concept:bite", "ctx:today", "participates-in"),
            ),
        )

        self.assertNotIn("value:green", {factor.value_ref for factor in today.factors})
        self.assertIn("value:green", {factor.value_ref for factor in yesterday.factors})
        self.assertLess(self.core.forms.similarity(yesterday.vector, today.vector), 0.9)
        self.assertEqual(
            {trace.input_factor_ref for trace in self.core.explain_form("form:apple-today")},
            {"new:identity", "new:patient"},
        )

    def test_anchor_generation_is_deterministic(self) -> None:
        left = self.core.forms.anchor("value:example")
        other_core = DevelopmentalCore(vector_dimension=2048, seed="test-core")
        right = other_core.forms.anchor("value:example")
        self.assertTrue((left == right).all())

    def test_full_core_snapshot_rebuilds_relations_forms_memory_and_traces(self) -> None:
        self.core.universe.add_identity(
            IdentityAnchor("person:maya", "ctx:today", ("obs:maya",), ("Maya",))
        )
        self.core.universe.add_relation(
            RelationOccurrence(
                "relation:agent-1",
                "relation:participation",
                (
                    RoleBinding("participant", "person:maya"),
                    RoleBinding("role", "role:agent"),
                ),
                "ctx:today",
                1,
                Polarity.POSITIVE,
                "actual",
                None,
                ("obs:event",),
                (),
                EpistemicState.OBSERVED,
            )
        )
        form = self.core.encode_form(
            "form:maya",
            (
                FormFactor(
                    "factor:maya", "person:maya", "ctx:today", "identity", support_refs=("obs:maya",)
                ),
            ),
        )
        self.core.memory.remember(
            form.form_id,
            kind="form",
            features=("identity:maya", "role:agent"),
            context_refs=("ctx:today",),
            support_refs=("obs:maya",),
        )
        restored = DevelopmentalCore.restore(self.core.as_dict())

        self.assertEqual(restored.as_dict(), self.core.as_dict())
        self.assertTrue(
            restored.forms.equivalent(
                restored.forms.get("form:maya"), self.core.forms.get("form:maya")
            )
        )
        self.assertEqual(
            restored.universe.query_relations(
                relation_form_ref="relation:participation", context_ref="ctx:today"
            )[0].relation_occurrence_id,
            "relation:agent-1",
        )
        self.assertTrue(restored.memory.accessible("form:maya"))


if __name__ == "__main__":
    unittest.main()
