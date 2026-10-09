"""POC-12 tests over the cached real observations."""

from pathlib import Path
import random

import pytest

from research.induction import IncrementalStructuralIndex, batch_signature_groups
from research.induction.corpus_evidence import load_real_corpus


CACHE = Path(__file__).resolve().parents[2] / ".local/cache/seman2/induction"
GRAPHS = load_real_corpus(CACHE)


def test_incremental_groups_equal_batch_groups():
    index = IncrementalStructuralIndex(min_support=4)
    for graph in GRAPHS:
        index.ingest(graph)
    incremental = {row.signature: row.member_ids for row in index.active_components}
    assert incremental == batch_signature_groups(GRAPHS, min_support=4)


def test_component_result_is_stable_under_stream_permutation():
    expected = set(batch_signature_groups(GRAPHS, min_support=4))
    for seed in (1, 7, 31):
        shuffled = list(GRAPHS)
        random.Random(seed).shuffle(shuffled)
        index = IncrementalStructuralIndex(min_support=4)
        for graph in shuffled:
            index.ingest(graph)
        assert {row.signature for row in index.active_components} == expected


def test_neighbor_comparisons_are_below_all_pairs():
    index = IncrementalStructuralIndex(min_support=4)
    comparisons = sum(index.ingest(graph).comparisons for graph in GRAPHS)
    assert comparisons < len(GRAPHS) * (len(GRAPHS) - 1) // 2


def test_snapshot_roundtrip_preserves_components_and_cache():
    index = IncrementalStructuralIndex(min_support=4)
    for graph in GRAPHS[:200]:
        index.ingest(graph)
    restored = IncrementalStructuralIndex.from_dict(index.as_dict())
    assert restored.as_dict() == index.as_dict()


def test_late_invalidations_retire_without_erasing_lineage():
    index = IncrementalStructuralIndex(min_support=4)
    for graph in GRAPHS:
        index.ingest(graph)
    component = index.active_components[0]
    for observation_id in component.member_ids[:-3]:
        index.invalidate(observation_id)
    latest = max(
        (row for row in index.revisions if row.component_id == component.component_id),
        key=lambda row: row.version,
    )
    assert latest.status == "retired"
    assert latest.parent_version is not None
    assert any(row.status == "active" for row in index.revisions if row.component_id == component.component_id)


def test_duplicate_observation_is_rejected():
    index = IncrementalStructuralIndex()
    index.ingest(GRAPHS[0])
    with pytest.raises(ValueError, match="duplicate"):
        index.ingest(GRAPHS[0])
