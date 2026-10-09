"""POC-10 tests for immutable revision and contextual splitting."""

import pytest

from research.induction import HypothesisReviser, RevisionEvidence


def evidence(prefix, hypothesis, context, supports, count, reliability=1.0):
    return [
        RevisionEvidence(f"{prefix}-{index}", hypothesis, context, supports, prefix, reliability)
        for index in range(count)
    ]


def test_counterexamples_retire_parent_and_preserve_supported_specialization():
    reviser = HypothesisReviser(min_support=5, min_confidence=0.8)
    initial = evidence("old-p", "h", "physical", True, 10) + evidence("old-i", "h", "idiom", True, 10)
    first = reviser.register("h", {"kind": "equivalence"}, initial)
    created = reviser.revise(
        "h",
        evidence("new-p", "h", "physical", False, 10)
        + evidence("new-i", "h", "idiom", True, 10),
    )
    retired, child = created
    assert retired.status == "retired"
    assert retired.parent_revision_id == first.revision_id
    assert child.status == "active"
    assert child.context_id == "idiom"
    assert child.specialization_of == "h"
    assert child.payload == first.payload


def test_unreliable_source_is_audited_but_does_not_invalidate():
    reviser = HypothesisReviser(min_support=5, min_confidence=0.8, min_source_reliability=0.5)
    reviser.register("h", {"rule": "opaque"}, evidence("trusted", "h", "main", True, 8))
    revision = reviser.revise("h", evidence("fiction", "h", "main", False, 20, reliability=0.1))[0]
    assert revision.status == "active"
    assert len(revision.ignored_evidence_ids) == 20
    assert revision.confidence == 1.0


def test_all_versions_and_raw_evidence_ids_remain_in_lineage():
    reviser = HypothesisReviser(min_support=2, min_confidence=0.75)
    reviser.register("h", {"x": 1}, evidence("a", "h", "c", True, 3))
    reviser.revise("h", evidence("b", "h", "c", True, 2))
    lineage = reviser.lineage("h")
    assert [row.version for row in lineage] == [1, 2]
    assert set(lineage[-1].evidence_ids) == {"a-0", "a-1", "a-2", "b-0", "b-1"}


def test_duplicate_evidence_is_rejected():
    reviser = HypothesisReviser(min_support=2)
    rows = evidence("e", "h", "c", True, 2)
    reviser.register("h", {}, rows)
    with pytest.raises(ValueError, match="duplicate evidence"):
        reviser.revise("h", rows[:1])
