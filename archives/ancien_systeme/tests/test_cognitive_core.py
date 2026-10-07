from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from seman2_runtime import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveRuntime,
    ContractError,
    ControlState,
    ModuleSpec,
    Residency,
    SafetyLimits,
)
from seman2_runtime.cognitive_ingestion import (
    IngestionPolicy,
    IngestionRecord,
    build_foundation_runtime,
    ingest_records,
    records_from_dictionary_file,
    records_from_text_file,
)
from seman2_runtime.cognitive_formal_analysis import (
    FormalAnalysisPolicy,
    _select_diverse_active_candidates,
    build_formal_runtime,
)
from seman2_runtime.cognitive_ingestion_session import CognitiveIngestionSession
from seman2_runtime.cognitive_ingestion_validation import assess_cognitive_ingestion
from seman2_runtime.control_state import CognitiveParameters
from seman2_runtime.developmental_core import (
    ContextFrame,
    ContextKind,
    DevelopmentalCore,
    EpistemicState,
)
from seman2_runtime.formal_core_adapter import adapt_semantic_artifacts


CONFIG = hashlib.sha256(b"test-cognitive-core").hexdigest()
BUILD = "test-build"


def proposal(
    artifact_type: str,
    producer_id: str,
    session_id: str,
    wave: int,
    parent_ids: tuple[str, ...],
    idempotency_key: str,
    payload: dict,
    *,
    activation: float = 1.0,
) -> ArtifactProposal:
    return ArtifactProposal(
        artifact_type=artifact_type,
        producer_id=producer_id,
        producer_build=BUILD,
        configuration_digest=CONFIG,
        mode="ingestion",
        session_id=session_id,
        wave=wave,
        parent_ids=parent_ids,
        payload_native=payload,
        payload_projection={"summary": artifact_type},
        idempotency_key=idempotency_key,
        activation=activation,
    )


def build_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    registry.register(
        ArtifactTypeSpec(
            "raw", "raw", 0, root_allowed=True, allowed_producers=frozenset({"input"})
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "observation",
            "observation",
            1,
            allowed_producers=frozenset({"observer"}),
            parent_types=frozenset({"raw"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "syntax",
            "syntax",
            2,
            allowed_producers=frozenset({"syntactic"}),
            parent_types=frozenset({"observation"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "temporal",
            "temporal",
            2,
            allowed_producers=frozenset({"temporal"}),
            parent_types=frozenset({"observation"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "attention",
            "attention",
            2,
            allowed_producers=frozenset({"feedback"}),
            feedback_parent_types=frozenset({"belief"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "integrated",
            "integrated",
            3,
            allowed_producers=frozenset({"integrator"}),
            parent_types=frozenset({"syntax", "temporal"}),
        )
    )
    registry.register(
        ArtifactTypeSpec(
            "belief",
            "belief",
            4,
            allowed_producers=frozenset({"reasoner"}),
            parent_types=frozenset({"integrated"}),
        )
    )
    registry.freeze()
    return registry


def build_modules() -> tuple[ModuleSpec, ...]:
    def observer(trigger, context):
        yield proposal(
            "observation",
            "observer",
            trigger.session_id,
            context.scheduled_wave,
            (trigger.artifact_id,),
            f"observe:{trigger.artifact_id}",
            {"text": trigger.payload_native["text"]},
        )

    def syntactic(trigger, context):
        yield proposal(
            "syntax",
            "syntactic",
            trigger.session_id,
            context.scheduled_wave,
            (trigger.artifact_id,),
            f"syntax:{trigger.artifact_id}",
            {"dependencies": [["chat", "dort"]]},
        )

    def temporal(trigger, context):
        yield proposal(
            "temporal",
            "temporal",
            trigger.session_id,
            context.scheduled_wave,
            (trigger.artifact_id,),
            f"temporal:{trigger.artifact_id}",
            {"interval": "now"},
        )

    def integrator(trigger, context):
        observation_id = trigger.parent_ids[0]
        syntax = [
            row
            for row in context.arena.query(
                artifact_type="syntax",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
                residency=Residency.ACTIVE,
            )
            if observation_id in row.parent_ids
        ]
        temporal_rows = [
            row
            for row in context.arena.query(
                artifact_type="temporal",
                session_id=trigger.session_id,
                wave_at_most=context.scheduled_wave,
                residency=Residency.ACTIVE,
            )
            if observation_id in row.parent_ids
        ]
        if not syntax or not temporal_rows:
            return
        parents = tuple(sorted((syntax[0].artifact_id, temporal_rows[0].artifact_id)))
        yield proposal(
            "integrated",
            "integrator",
            trigger.session_id,
            context.scheduled_wave,
            parents,
            f"integrated:{observation_id}",
            {"event": "sleep", "tense": temporal_rows[0].payload_native["interval"]},
        )

    def reasoner(trigger, context):
        yield proposal(
            "belief",
            "reasoner",
            trigger.session_id,
            context.scheduled_wave,
            (trigger.artifact_id,),
            f"belief:{trigger.artifact_id}",
            {"predicate": "sleeping(cat)"},
        )

    def feedback(trigger, context):
        yield proposal(
            "attention",
            "feedback",
            trigger.session_id,
            context.scheduled_wave,
            (trigger.artifact_id,),
            f"feedback:{trigger.artifact_id}",
            {"boost": "cat"},
        )

    def spec(module_id, layer, consumes, produces, handler, *, delay=0):
        return ModuleSpec(
            module_id=module_id,
            layer=layer,
            modes=frozenset({"ingestion", "chatbot"}),
            consumes=frozenset(consumes),
            produces=frozenset(produces),
            producer_build=BUILD,
            configuration_digest=CONFIG,
            handler=handler,
            feedback_delay=delay,
        )

    return (
        spec("observer", 1, {"raw"}, {"observation"}, observer),
        spec("syntactic", 2, {"observation"}, {"syntax"}, syntactic),
        spec("temporal", 2, {"observation"}, {"temporal"}, temporal),
        spec("integrator", 3, {"syntax", "temporal"}, {"integrated"}, integrator),
        spec("reasoner", 4, {"integrated"}, {"belief"}, reasoner),
        spec("feedback", 2, {"belief"}, {"attention"}, feedback, delay=1),
    )


def root_proposal(*, session: str = "session-1", activation: float = 1.0):
    return proposal(
        "raw",
        "input",
        session,
        0,
        (),
        f"input:{session}",
        {"text": "Le chat dort maintenant.", "nested": {"tokens": ["Le", "chat"]}},
        activation=activation,
    )


class CognitiveCoreTests(unittest.TestCase):
    def test_soar_active_projection_reserves_structural_diversity(self):
        candidates = [
            {
                "hypothesis_ref": "H1",
                "structural_features": ["root:event", "edge:agent"],
            },
            {
                "hypothesis_ref": "H2",
                "structural_features": ["root:event", "edge:agent"],
            },
            {
                "hypothesis_ref": "H3",
                "structural_features": ["root:entity", "edge:property"],
            },
        ]
        active, inactive = _select_diverse_active_candidates(candidates, 2)
        self.assertEqual([row["hypothesis_ref"] for row in active], ["H1", "H3"])
        self.assertEqual([row["hypothesis_ref"] for row in inactive], ["H2"])

    def test_code_observation_is_routed_to_tree_sitter_without_text_parsers(self):
        root = Path(__file__).resolve().parent.parent
        fixture_path = root / "poc/code-01/fixtures.json"
        if not fixture_path.is_file():
            self.skipTest("fixtures Tree-sitter absentes")
        fixture = json.loads(fixture_path.read_text())[0]
        policy = IngestionPolicy(max_records=1, max_text_chars=5_000)
        runtime = build_formal_runtime(
            root,
            ingestion_policy=policy,
            formal_policy=FormalAnalysisPolicy(max_units_per_observation=1),
        )
        record = IngestionRecord(
            record_id="code:real-fixture",
            discourse_id="code:fixture",
            turn_index=0,
            speaker_role="author",
            text=fixture["text"],
            canonical_file=str(fixture_path),
            source_position=0,
            source_record_id=fixture["id"],
            raw_body_sha256=hashlib.sha256(fixture["text"].encode()).hexdigest(),
            channel="code",
            source_kind="code",
            native_structure={"programming_language": fixture["language"]},
        )
        ingest_records(runtime, (record,), policy=policy, session_id="test:code-routing")
        analyses = runtime.arena.query(artifact_type="code-analysis")
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0].payload_native["status"], "parsed")
        self.assertTrue(analyses[0].payload_native["source_reconstructed"])
        self.assertEqual(len(runtime.arena.query(artifact_type="mrs-analysis")), 0)
        routing = runtime.arena.query(artifact_type="analysis-routing-state")
        self.assertEqual(routing[0].payload_native["routed_analyzers"], ("code",))
        ledger = runtime.arena.query(artifact_type="native-analysis-ledger-entry")
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0].payload_native["analysis_type"], "code-analysis")
        cross = runtime.arena.query(artifact_type="cross-representation-hypothesis")
        self.assertEqual(len(cross), 1)
        self.assertEqual(cross[0].payload_native["analysis_refs"], (ledger[0].artifact_id,))

    def test_two_real_observations_build_factorized_reference_continuity(self):
        root = Path(__file__).resolve().parent.parent
        novel = root / "data/the_map_of_everything_nlp_novel.txt"
        required = [novel, root / ".venv-dialogue/bin/python", root / ".local/bin/ace"]
        if not all(path.is_file() for path in required):
            self.skipTest("roman ou analyseurs formels absents")
        sentences = (
            "Maya drew the old lot beside the apartment building, where weeds pushed through the fence.",
            "Maya carried a blue notebook home.",
        )
        locations = {}
        with novel.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                for sentence in sentences:
                    if sentence in line:
                        locations[sentence] = number
        self.assertEqual(set(locations), set(sentences))
        ingestion_policy = IngestionPolicy(max_records=2, max_text_chars=500)
        runtime = build_formal_runtime(
            root,
            ingestion_policy=ingestion_policy,
            formal_policy=FormalAnalysisPolicy(max_units_per_observation=1),
            control=ControlState(
                limits=SafetyLimits(max_worker_count=4),
                parameters=CognitiveParameters(induction_trigger=2),
            ),
        )
        records = tuple(
            IngestionRecord(
                record_id=f"continuity:{index}",
                discourse_id="text:the-map-of-everything",
                turn_index=index,
                speaker_role="narrator",
                text=sentence,
                canonical_file=str(novel),
                source_position=locations[sentence],
                source_record_id=f"line:{locations[sentence]}",
                raw_body_sha256=hashlib.sha256(sentence.encode()).hexdigest(),
                channel="narrative-text",
                source_kind="sentence",
            )
            for index, sentence in enumerate(sentences)
        )
        session = CognitiveIngestionSession(
            runtime=runtime,
            records=records,
            policy=ingestion_policy,
            session_id="test:reference-continuity",
        )
        self.assertEqual(session.run(), 2)
        references = runtime.arena.query(artifact_type="reference-state-candidate")
        second = [row for row in references if row.wave == 1]
        self.assertEqual(len(runtime.arena.query(artifact_type="hypothesis-family")), 2)
        self.assertEqual(len(runtime.arena.query(artifact_type="episode-candidate")), 2)
        dialogue_states = runtime.arena.query(artifact_type="dialogue-state-candidate")
        self.assertEqual(len(dialogue_states), 2)
        self.assertEqual(
            dialogue_states[-1].payload_native["prior_dialogue_refs"],
            (dialogue_states[0].artifact_id,),
        )
        self.assertFalse(dialogue_states[-1].payload_native["grounding_committed"])
        self.assertTrue(second)
        self.assertTrue(all(row.payload_native["mentions"] for row in second))
        self.assertTrue(all(row.payload_native["prior_candidate_refs"] for row in second))
        self.assertTrue(all(row.payload_native["identity_asserted"] is False for row in second))
        indexes = runtime.arena.query(artifact_type="retrieval-index-entry")
        statistics = runtime.arena.query(artifact_type="statistics-snapshot")
        inductions = runtime.arena.query(artifact_type="induction-state")
        cultures = runtime.arena.query(artifact_type="cultural-learning-state")
        learned_concepts = runtime.arena.query(
            artifact_type="learned-concept-candidate"
        )
        transformation_decisions = runtime.arena.query(
            artifact_type="soar-transformation-decision"
        )
        consolidation_states = runtime.arena.query(
            artifact_type="memory-consolidation-state"
        )
        self.assertEqual(len(indexes), 2)
        self.assertTrue(all(row.payload_projection["internal_references_only"] for row in indexes))
        self.assertEqual(statistics[-1].payload_native["episode_count"], 2)
        self.assertEqual(statistics[-1].payload_native["feature_support"]["constant:maya"], 2)
        self.assertIn(
            "constant:maya",
            {row["feature"] for row in inductions[-1].payload_native["pattern_candidates"]},
        )
        self.assertTrue(inductions[-1].payload_native["promoted_patterns"])
        self.assertEqual(
            cultures[-1].payload_native["status"], "anonymous-candidates-created"
        )
        self.assertEqual(cultures[-1].payload_native["concepts_asserted"], ())
        maya_candidates = [
            row
            for row in learned_concepts
            if row.payload_native["source_feature"] == "constant:maya"
        ]
        self.assertEqual(len(maya_candidates), 1)
        self.assertFalse(maya_candidates[0].payload_native["asserted"])
        self.assertFalse(maya_candidates[0].payload_native["meaning_assigned"])
        self.assertEqual(len(transformation_decisions), 2)
        self.assertTrue(
            all(
                row.payload_native["transformation_kind"] == "retain-episode"
                for row in transformation_decisions
            )
        )
        self.assertEqual(len(consolidation_states), 2)
        self.assertTrue(
            all(row.payload_native["applied"] for row in consolidation_states)
        )
        self.assertTrue(
            all(not row.payload_native["truth_committed"] for row in consolidation_states)
        )

    def test_ingestion_session_checkpoint_resumes_exact_source_cursor(self):
        source = Path(__file__).resolve().parent.parent / "data/the_map_of_everything_nlp_novel.txt"
        if not source.is_file():
            self.skipTest("fixture textuelle réelle absente")
        policy = IngestionPolicy(max_records=4, max_text_chars=2_000)
        records = records_from_text_file(source, policy=policy)

        baseline_runtime = build_foundation_runtime(policy)
        baseline = CognitiveIngestionSession(
            runtime=baseline_runtime,
            records=records,
            policy=policy,
            session_id="test:session-resume",
        )
        self.assertEqual(baseline.run(), 4)

        interrupted_runtime = build_foundation_runtime(policy)
        interrupted = CognitiveIngestionSession(
            runtime=interrupted_runtime,
            records=records,
            policy=policy,
            session_id="test:session-resume",
        )
        self.assertEqual(interrupted.run(max_records=2), 2)
        self.assertEqual(interrupted.next_record_index, 2)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "ingestion.json"
            interrupted.checkpoint(checkpoint)
            resumed = CognitiveIngestionSession.restore(
                checkpoint,
                records=records,
                registry=interrupted_runtime.registry,
                modules=interrupted_runtime.modules,
            )
            self.assertEqual(resumed.next_record_index, 2)
            self.assertEqual(resumed.run(), 2)
            self.assertTrue(resumed.complete)

        self.assertEqual(resumed.runtime.arena.as_dict(), baseline.runtime.arena.as_dict())
        self.assertEqual(
            resumed.runtime.scheduler.as_dict(), baseline.runtime.scheduler.as_dict()
        )

    def test_real_novel_sentence_reaches_isolated_formal_analyzers(self):
        root = Path(__file__).resolve().parent.parent
        novel = root / "data/the_map_of_everything_nlp_novel.txt"
        required = [
            novel,
            root / ".venv-dialogue/bin/python",
            root / ".local/bin/ace",
            root / ".local/share/erg/erg-2018-x86-64-0.9.34.dat",
        ]
        if not all(path.is_file() for path in required):
            self.skipTest("roman ou analyseurs formels absents")
        sentence = "Maya carried a blue notebook home."
        with novel.open(encoding="utf-8") as handle:
            source_line = next(
                number
                for number, line in enumerate(handle, start=1)
                if sentence in line
            )
        ingestion_policy = IngestionPolicy(max_records=1, max_text_chars=500)
        runtime = build_formal_runtime(
            root,
            ingestion_policy=ingestion_policy,
            formal_policy=FormalAnalysisPolicy(max_units_per_observation=1),
        )
        record = IngestionRecord(
            record_id="map:real-sentence",
            discourse_id="text:the-map-of-everything",
            turn_index=0,
            speaker_role="narrator",
            text=sentence,
            canonical_file=str(novel),
            source_position=source_line,
            source_record_id="sentence:maya-notebook",
            raw_body_sha256=hashlib.sha256(sentence.encode()).hexdigest(),
            channel="narrative-text",
            source_kind="sentence",
            native_structure={"selected_from_real_document": True},
        )
        session = CognitiveIngestionSession(
            runtime=runtime,
            records=(record,),
            policy=ingestion_policy,
            session_id="test:formal-map",
        )
        self.assertEqual(session.run(), 1)
        report = assess_cognitive_ingestion(
            session,
            records_processed_this_run=1,
            input_path=novel,
            input_format="text",
        )
        self.assertEqual(report["status"], "GO-INGESTION-SYSTEM")
        self.assertEqual(report["missing_required_modules"], [])
        self.assertTrue(report["every_terminal_has_complete_bottom_up_lineage"])
        self.assertEqual(
            report["terminal_bottom_up_lineages"][0]["ancestry_size"], 51
        )
        mrs = runtime.arena.query(artifact_type="mrs-analysis")
        dynamic = runtime.arena.query(artifact_type="dynamic-syntax-analysis")
        linkages = runtime.arena.query(artifact_type="linkage-analysis")
        lexical = runtime.arena.query(artifact_type="lexical-analysis")
        form_phonology = runtime.arena.query(artifact_type="form-phonology-analysis")
        cross_representation = runtime.arena.query(
            artifact_type="cross-representation-hypothesis"
        )
        routing = runtime.arena.query(artifact_type="analysis-routing-state")
        ledger = runtime.arena.query(artifact_type="native-analysis-ledger-entry")
        fragments = runtime.arena.query(artifact_type="graph-fragment")
        semantics = runtime.arena.query(artifact_type="semantic-structure")
        developmental = DevelopmentalCore(vector_dimension=512, seed="real-mrs")
        developmental.universe.add_context(
            ContextFrame("ctx:real-observation", ContextKind.NARRATED)
        )
        adapted_semantics = adapt_semantic_artifacts(
            developmental,
            semantics,
            parent_context_ref="ctx:real-observation",
            temporal_index=0,
        )
        temporal_networks = runtime.arena.query(
            artifact_type="temporal-constraint-network"
        )
        constraint_solutions = runtime.arena.query(artifact_type="constraint-solution")
        hypotheses = runtime.arena.query(artifact_type="hypothesis-candidate")
        families = runtime.arena.query(artifact_type="hypothesis-family")
        situations = runtime.arena.query(artifact_type="situation-branch-set")
        episodes = runtime.arena.query(artifact_type="episode-candidate")
        soar_states = runtime.arena.query(artifact_type="soar-control-state")
        dialogue_states = runtime.arena.query(artifact_type="dialogue-state-candidate")
        cultures = runtime.arena.query(artifact_type="cultural-learning-state")
        transformations = runtime.arena.query(
            artifact_type="state-transformation-candidate"
        )
        transformation_decisions = runtime.arena.query(
            artifact_type="soar-transformation-decision"
        )
        consolidation_states = runtime.arena.query(
            artifact_type="memory-consolidation-state"
        )
        self.assertEqual(len(mrs), 1)
        self.assertEqual(mrs[0].payload_native["status"], "parsed")
        self.assertEqual(mrs[0].payload_native["candidate_count"], 3)
        self.assertTrue(all(row["mrs"] for row in mrs[0].payload_native["candidates"]))
        self.assertEqual(len(dynamic), 1)
        self.assertIn(dynamic[0].payload_native["status"], {"parsed", "failure"})
        self.assertEqual(len(linkages), 1)
        self.assertEqual(linkages[0].payload_native["status"], "parsed")
        self.assertGreater(linkages[0].payload_native["linkage_count"], 0)
        self.assertEqual(len(ledger), 5)
        self.assertEqual(
            {row.payload_native["analysis_type"] for row in ledger},
            {
                "mrs-analysis",
                "dynamic-syntax-analysis",
                "linkage-analysis",
                "lexical-analysis",
                "form-phonology-analysis",
            },
        )
        self.assertEqual(len(lexical), 1)
        self.assertEqual(lexical[0].payload_native["status"], "analyzed")
        self.assertGreater(lexical[0].payload_native["occurrence_count"], 0)
        self.assertTrue(
            any(row["wordnet"] for row in lexical[0].payload_native["occurrences"])
        )
        self.assertEqual(
            set(lexical[0].payload_native["providers"].values()), {"queried"}
        )
        carried = next(
            row
            for row in lexical[0].payload_native["occurrences"]
            if row["form"] == "carried"
        )
        self.assertTrue(carried["framenet_candidates"])
        self.assertTrue(carried["semlink_mappings"])
        self.assertTrue(
            any(synset["sumo_mappings"] for synset in carried["wordnet"])
        )
        self.assertEqual(len(form_phonology), 1)
        self.assertIn(
            form_phonology[0].payload_native["status"], {"analyzed", "failure"}
        )
        self.assertGreater(form_phonology[0].payload_native["occurrence_count"], 0)
        home_form = next(
            row
            for row in form_phonology[0].payload_native["occurrences"]
            if row["form"] == "home"
        )
        self.assertTrue(home_form["g2p_candidates"])
        if form_phonology[0].payload_native["status"] == "failure":
            self.assertTrue(form_phonology[0].payload_native["errors"])
        self.assertTrue(
            all(row.payload_projection["cross_producer_ranking_performed"] is False for row in ledger)
        )
        self.assertEqual(len(cross_representation), 1)
        self.assertEqual(
            set(routing[0].payload_native["routed_analyzers"]),
            {"erg", "dynamic-syntax", "link-grammar", "lexical", "form-phonology"},
        )
        self.assertEqual(
            {row["analyzer"] for row in routing[0].payload_native["skipped_analyzers"]},
            {"code", "temporal-surface", "rst"},
        )
        self.assertEqual(len(cross_representation[0].payload_native["analysis_refs"]), 5)
        self.assertGreater(len(cross_representation[0].payload_native["alignments"]), 0)
        self.assertEqual(
            (len(fragments), len(semantics), len(temporal_networks), len(hypotheses)),
            (3, 3, 3, 3),
        )
        self.assertEqual(len(constraint_solutions), 3)
        self.assertTrue(
            all(row.payload_native["status"] == "SAT" for row in constraint_solutions)
        )
        self.assertTrue(all(row.payload_native["predicates"] for row in semantics))
        self.assertEqual(len(adapted_semantics), len(semantics))
        self.assertTrue(all(bundle.relation_refs for bundle in adapted_semantics))
        self.assertTrue(all(bundle.distributed_form_refs for bundle in adapted_semantics))
        self.assertEqual(
            len({bundle.context_ref for bundle in adapted_semantics}), len(semantics)
        )
        self.assertTrue(
            all(
                developmental.universe.relations[relation_ref].epistemic_state
                is EpistemicState.HYPOTHESIS
                for bundle in adapted_semantics
                for relation_ref in bundle.relation_refs
            )
        )
        self.assertEqual(
            developmental.universe.query_relations(
                context_ref="ctx:real-observation"
            ),
            (),
        )
        self.assertTrue(all(row.payload_native["tense"] == "past" for row in temporal_networks))
        self.assertTrue(
            all(
                row.payload_native["constraints"][1]["operator"] == "<"
                for row in temporal_networks
            )
        )
        self.assertTrue(all(row.payload_native["selected"] is False for row in hypotheses))
        self.assertTrue(
            all(
                row.payload_projection["cross_candidate_product_materialized"] is False
                for row in hypotheses
            )
        )
        self.assertEqual((len(families), len(situations), len(episodes)), (1, 1, 1))
        self.assertEqual(len(dialogue_states), 1)
        self.assertTrue(dialogue_states[0].payload_native["dialogue_act_candidates"])
        self.assertFalse(dialogue_states[0].payload_native["grounding_committed"])
        self.assertFalse(dialogue_states[0].payload_projection["raw_source_read"])
        self.assertEqual(len(families[0].payload_native["member_refs"]), 3)
        self.assertIsNone(families[0].payload_native["selected_ref"])
        self.assertEqual(len(situations[0].payload_native["branches"]), 3)
        self.assertIsNone(situations[0].payload_native["committed_ref"])
        self.assertFalse(episodes[0].payload_native["committed"])
        self.assertEqual(cultures[0].payload_native["status"], "insufficient-support")
        self.assertEqual(
            len(runtime.arena.query(artifact_type="learned-concept-candidate")), 0
        )
        self.assertEqual(len(transformations), 2)
        self.assertEqual(
            {row.payload_native["kind"] for row in transformations},
            {"retain-episode", "defer-consolidation"},
        )
        self.assertTrue(
            all(not row.payload_projection["uses_raw_source"] for row in transformations)
        )
        self.assertEqual(len(transformation_decisions), 1)
        self.assertTrue(
            transformation_decisions[0].payload_native["selection_is_operational"]
        )
        self.assertFalse(
            transformation_decisions[0].payload_native["semantic_truth_selected"]
        )
        self.assertTrue(
            transformation_decisions[0].payload_native[
                "all_required_refs_observed_in_wm"
            ]
        )
        self.assertEqual(
            transformation_decisions[0].payload_native[
                "projected_precondition_ref_count"
            ],
            3,
        )
        self.assertEqual(len(consolidation_states), 1)
        self.assertTrue(consolidation_states[0].payload_native["applied"])
        self.assertFalse(consolidation_states[0].payload_native["truth_committed"])
        cultural_ancestry = {
            row.artifact_type
            for row in runtime.arena.ancestry(cultures[0].artifact_id)
        }
        self.assertTrue(
            {
                "mrs-analysis",
                "dynamic-syntax-analysis",
                "linkage-analysis",
                "lexical-analysis",
                "form-phonology-analysis",
                "cross-representation-hypothesis",
                "semantic-structure",
                "temporal-constraint-network",
                "constraint-solution",
                "hypothesis-family",
                "soar-control-state",
                "discourse-state-candidate",
                "dialogue-state-candidate",
                "episode-candidate",
                "statistics-snapshot",
                "induction-state",
                "cultural-learning-state",
                "state-transformation-candidate",
                "soar-transformation-decision",
                "memory-consolidation-state",
            }
            <= {
                row.artifact_type
                for row in runtime.arena.ancestry(consolidation_states[0].artifact_id)
            }
        )
        self.assertEqual(len(soar_states), 1)
        self.assertEqual(soar_states[0].payload_native["status"], "controlled")
        self.assertTrue(soar_states[0].payload_native["working_memory_verified"])
        self.assertFalse(soar_states[0].payload_native["selection_performed"])
        self.assertEqual(
            soar_states[0].payload_native["selection_policy"],
            "greedy-structural-diversity-stable",
        )
        self.assertEqual(
            soar_states[0].payload_native["projected_justification_ref_count"], 12
        )
        self.assertTrue(
            soar_states[0].payload_native["all_required_refs_observed_in_wm"]
        )
        self.assertTrue(soar_states[0].payload_native["inactive_refs_absent_from_wm"])
        self.assertFalse(
            soar_states[0].payload_projection["persistent_store_copied_to_soar"]
        )
        ancestry_types = {
            row.artifact_type for row in runtime.arena.ancestry(situations[0].artifact_id)
        }
        self.assertTrue(
            {
                "source-record",
                "observation",
                "observable-unit",
                "analysis-job-erg",
                "mrs-analysis",
                "native-analysis-ledger-entry",
                "analysis-routing-state",
                "cross-representation-hypothesis",
                "graph-fragment",
                "semantic-structure",
                "temporal-constraint-network",
                "constraint-solution",
                "hypothesis-candidate",
                "hypothesis-family",
                "soar-control-state",
                "discourse-state-candidate",
                "dialogue-state-candidate",
                "situation-branch-set",
            }
            <= ancestry_types
        )
        worker_frontier = next(
            row
            for row in runtime.scheduler.trace
            if {task["module_id"] for task in row["parallel_tasks"]}
            == {
                "erg-worker",
                "dynamic-syntax-worker",
                "link-grammar-worker",
                "lexical-resource-worker",
                "form-phonology-worker",
            }
        )
        self.assertEqual(len(worker_frontier["parallel_tasks"]), 5)
        self.assertEqual(worker_frontier["execution"], "concurrent")
        self.assertEqual(worker_frontier["worker_count"], 4)

    def test_dictionary_is_ingested_as_input_not_as_lexical_truth(self):
        source = Path(__file__).resolve().parent.parent / "data/english-dictionary.jsonl"
        if not source.is_file():
            self.skipTest("corpus dictionnaire JSONL absent")
        policy = IngestionPolicy(max_records=8, max_text_chars=5_000)
        records = records_from_dictionary_file(source, policy=policy)
        self.assertEqual(len(records), 8)
        self.assertTrue(all(row.channel == "dictionary-corpus" for row in records))
        self.assertTrue(all(row.source_kind == "dictionary-sense" for row in records))

        runtime = build_foundation_runtime(policy)
        report = ingest_records(
            runtime,
            records,
            policy=policy,
            session_id="test:dictionary-ingestion",
        )
        observations = runtime.arena.query(artifact_type="observation")
        self.assertEqual(report["observations_created"], 8)
        self.assertEqual(len(observations), 8)
        self.assertTrue(
            all(row.payload_native["channel"] == "dictionary-corpus" for row in observations)
        )
        self.assertTrue(
            all(row.payload_native["native_structure"]["sense"] for row in observations)
        )
        self.assertEqual(
            {row.artifact_type for row in runtime.arena.query()},
            {"source-record", "observation"},
        )

    def test_real_lightweight_text_is_ingested_sequentially_and_bounded(self):
        source = Path(__file__).resolve().parent.parent / "data/the_map_of_everything_nlp_novel.txt"
        if not source.is_file():
            self.skipTest("fixture textuelle réelle absente")
        policy = IngestionPolicy(max_records=12, max_text_chars=2_000)
        records = records_from_text_file(source, policy=policy)
        runtime = build_foundation_runtime(policy)
        report = ingest_records(
            runtime,
            records,
            policy=policy,
            session_id="test:map-of-everything",
        )

        self.assertEqual(len(records), 12)
        self.assertLessEqual(sum(len(row.text) for row in records), 24_000)
        self.assertEqual(report["status"], "GO-SOURCE-OBSERVATION")
        self.assertEqual(report["records_ingested"], 12)
        self.assertEqual(report["observations_created"], 12)
        self.assertEqual(report["pending_tasks"], 0)
        self.assertFalse(report["labels_or_votes_in_cognitive_payload"])
        sources = runtime.arena.query(artifact_type="source-record")
        observations = runtime.arena.query(artifact_type="observation")
        self.assertEqual([row.wave for row in observations], list(range(12)))
        self.assertTrue(
            all(row.parent_ids == (source_row.artifact_id,) for row, source_row in zip(observations, sources))
        )
        self.assertTrue(all(row.payload_native["speaker_role"] == "narrator" for row in observations))

    def test_artifacts_are_deeply_immutable_and_idempotent(self):
        arena = ArtifactArena(build_registry())
        source = {"text": "Le chat dort.", "nested": {"tokens": ["chat"]}}
        item = proposal("raw", "input", "s", 0, (), "input:s", source)
        artifact = arena.publish(item)
        source["nested"]["tokens"].append("altéré")

        self.assertEqual(artifact.payload_native["nested"]["tokens"], ("chat",))
        self.assertIs(arena.publish(item), artifact)
        conflict = proposal("raw", "input", "s", 0, (), "input:s", {"text": "autre"})
        with self.assertRaisesRegex(ContractError, "conflit d'idempotence"):
            arena.publish(conflict)

    def test_high_level_cannot_consume_raw_input(self):
        arena = ArtifactArena(build_registry())
        raw = arena.publish(root_proposal())
        shortcut = proposal(
            "belief",
            "reasoner",
            raw.session_id,
            0,
            (raw.artifact_id,),
            "illegal-shortcut",
            {"predicate": "guessed"},
        )
        with self.assertRaisesRegex(ContractError, "parent raw interdit"):
            arena.publish(shortcut)

    def test_parallel_low_level_branches_feed_real_high_level_matter(self):
        runtime = CognitiveRuntime(registry=build_registry(), modules=build_modules())
        runtime.submit(root_proposal())
        runtime.run()

        syntax = runtime.arena.query(artifact_type="syntax")
        temporal_rows = runtime.arena.query(artifact_type="temporal")
        integrated = runtime.arena.query(artifact_type="integrated")
        beliefs = runtime.arena.query(artifact_type="belief")
        self.assertEqual((len(syntax), len(temporal_rows), len(integrated), len(beliefs)), (1, 1, 1, 1))
        self.assertEqual(set(integrated[0].parent_ids), {syntax[0].artifact_id, temporal_rows[0].artifact_id})
        parallel_frontiers = [
            row for row in runtime.scheduler.trace if len(row["parallel_tasks"]) == 2
        ]
        self.assertTrue(parallel_frontiers)
        self.assertEqual(
            {task["module_id"] for task in parallel_frontiers[0]["parallel_tasks"]},
            {"syntactic", "temporal"},
        )

    def test_activation_threshold_stops_propagation_without_deleting_matter(self):
        runtime = CognitiveRuntime(registry=build_registry(), modules=build_modules())
        raw = runtime.submit(root_proposal(activation=0.01))
        self.assertEqual(runtime.arena.activation(raw.artifact_id).residency, Residency.LATENT)
        self.assertEqual(runtime.scheduler.pending_count, 0)
        self.assertEqual(runtime.run(), 0)
        self.assertEqual(len(runtime.arena), 1)

    def test_quiescent_memory_pressure_demotes_without_deleting(self):
        control = ControlState(parameters=CognitiveParameters(max_active_entities=3))
        runtime = CognitiveRuntime(
            registry=build_registry(), modules=build_modules(), control=control
        )
        runtime.submit(root_proposal())
        runtime.run()
        total = len(runtime.arena)
        self.assertGreater(total, 3)
        self.assertEqual(runtime.consolidate_active_memory(), total - 3)
        self.assertEqual(len(runtime.arena.query(residency=Residency.ACTIVE)), 3)
        self.assertEqual(len(runtime.arena.query(residency=Residency.LATENT)), total - 3)
        self.assertEqual(len(runtime.arena), total)

    def test_feedback_is_delayed_and_same_wave_feedback_is_rejected(self):
        runtime = CognitiveRuntime(registry=build_registry(), modules=build_modules())
        runtime.submit(root_proposal())
        runtime.run()
        belief = runtime.arena.query(artifact_type="belief")[0]
        attention = runtime.arena.query(artifact_type="attention")[0]
        self.assertEqual(attention.wave, belief.wave + 1)

        arena = ArtifactArena(build_registry())
        # Recrée une chaîne minimale valide dans l'arène pour tester la frontière temporelle.
        raw = arena.publish(root_proposal(session="direct"))
        observation = arena.publish(proposal("observation", "observer", "direct", 0, (raw.artifact_id,), "o", {"text": "x"}))
        syntax = arena.publish(proposal("syntax", "syntactic", "direct", 0, (observation.artifact_id,), "s", {"dependencies": []}))
        temporal_row = arena.publish(proposal("temporal", "temporal", "direct", 0, (observation.artifact_id,), "t", {"interval": "now"}))
        integrated = arena.publish(proposal("integrated", "integrator", "direct", 0, (syntax.artifact_id, temporal_row.artifact_id), "i", {"event": "x"}))
        belief = arena.publish(proposal("belief", "reasoner", "direct", 0, (integrated.artifact_id,), "b", {"predicate": "x"}))
        with self.assertRaisesRegex(ContractError, "minimum 1"):
            arena.publish(proposal("attention", "feedback", "direct", 0, (belief.artifact_id,), "a", {"boost": "x"}))

    def test_control_adjustments_cannot_escape_safety_envelope(self):
        state = ControlState(limits=SafetyLimits(max_derivation_depth=30))
        state.adjust(
            {"max_derivation_depth": 28, "activation_floor": 0.25},
            actor_id="metacontrol",
            wave=3,
            reason="charge élevée",
        )
        self.assertEqual(state.revision, 1)
        self.assertEqual(state.parameters.max_derivation_depth, 28)
        with self.assertRaisesRegex(ContractError, "hors enveloppe"):
            state.adjust(
                {"max_derivation_depth": 31},
                actor_id="metacontrol",
                wave=4,
                reason="tentative invalide",
            )
        self.assertEqual(state.revision, 1)

    def test_checkpoint_resume_preserves_pending_work_and_exact_result(self):
        registry = build_registry()
        modules = build_modules()
        baseline = CognitiveRuntime(registry=registry, modules=modules)
        baseline.submit(root_proposal(session="resume"))
        baseline.run()

        interrupted = CognitiveRuntime(registry=registry, modules=modules)
        interrupted.submit(root_proposal(session="resume"))
        self.assertEqual(interrupted.run(max_tasks=1), 1)
        self.assertEqual(interrupted.scheduler.pending_count, 2)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "runtime.json"
            interrupted.checkpoint(checkpoint)
            resumed = CognitiveRuntime.restore(
                checkpoint, registry=registry, modules=modules
            )
            self.assertEqual(resumed.scheduler.pending_count, 2)
            resumed.run()

        self.assertEqual(resumed.arena.as_dict(), baseline.arena.as_dict())
        self.assertEqual(resumed.scheduler.as_dict(), baseline.scheduler.as_dict())


if __name__ == "__main__":
    unittest.main()
