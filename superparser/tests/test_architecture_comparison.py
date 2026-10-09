"""POC-13 architecture comparison tests."""

from pathlib import Path

from research.induction import compare_architectures, default_candidates, topology_metrics
from research.induction.corpus_evidence import load_real_corpus


CACHE = Path(__file__).resolve().parents[2] / ".local/cache/seman2/induction"


def test_every_candidate_owns_every_capability_once():
    for candidate in default_candidates():
        candidate.validate()
        assert topology_metrics(candidate, failed_capabilities=("relations", "transitions"))["duplicated_primitive_count"] == 0


def test_same_measurements_are_replayed_for_every_candidate():
    measurements = {"real_observation_count": 849, "precision": 0.409}
    report = compare_architectures(measurements)
    assert all(row["measurements"] == measurements for row in report["candidates"])


def test_boundary_counts_are_monotonic_for_the_declared_topologies():
    rows = {
        candidate.candidate_id: topology_metrics(candidate, failed_capabilities=("relations", "transitions"))
        for candidate in default_candidates()
    }
    assert rows["A"]["cross_engine_dependency_count"] == 0
    assert rows["A"]["cross_engine_dependency_count"] < rows["B"]["cross_engine_dependency_count"]
    assert rows["B"]["cross_engine_dependency_count"] < rows["C"]["cross_engine_dependency_count"]


def test_b_is_minimal_split_that_contains_real_failures():
    rows = {
        candidate.candidate_id: topology_metrics(candidate, failed_capabilities=("relations", "transitions"))
        for candidate in default_candidates()
    }
    assert rows["B"]["maximum_failure_blast_radius"] < rows["A"]["maximum_failure_blast_radius"]
    assert rows["B"]["engine_count"] < rows["C"]["engine_count"]
    assert compare_architectures({"shared": True})["provisional_choice"] == "B"


def test_real_audit_source_contains_exactly_849_observations():
    graphs = load_real_corpus(CACHE, required=849)
    assert len(graphs) == 849
    assert all(not graph.forest_ids for graph in graphs)
