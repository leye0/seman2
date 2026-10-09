from __future__ import annotations

import unittest

from seman2_runtime.developmental_core import ContextFrame, ContextKind, DevelopmentalCore
from seman2_runtime.identity_resolution import IdentityResolver, MentionOccurrence


def mention(
    ref: str,
    alias: str,
    context: str,
    discourse: str,
    at: int,
    *,
    gender: str = "feminine",
) -> MentionOccurrence:
    return MentionOccurrence(
        mention_ref=ref,
        context_ref=context,
        discourse_ref=discourse,
        temporal_index=at,
        surface_aliases=(alias,),
        grammatical_features=(("gender", gender), ("number", "singular")),
        role_refs=("role:agent",),
        support_refs=(f"obs:{ref}",),
    )


class IdentityResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = DevelopmentalCore(vector_dimension=256)
        self.core.universe.add_context(ContextFrame("ctx:one", ContextKind.NARRATED))
        self.core.universe.add_context(ContextFrame("ctx:two", ContextKind.NARRATED))
        self.resolver = IdentityResolver(self.core)

    def test_repeated_nearby_name_reuses_identity_with_separate_facets(self) -> None:
        first = self.resolver.propose(mention("m1", "Maya", "ctx:one", "story", 1))
        profile = self.resolver.commit(first)
        second = self.resolver.propose(mention("m2", "Maya", "ctx:two", "story", 2))
        updated = self.resolver.commit(second)

        self.assertEqual(second.selected_identity_ref, profile.identity_ref)
        self.assertEqual(updated.identity_ref, profile.identity_ref)
        self.assertEqual(updated.mention_refs, ("m1", "m2"))
        facets = [
            row
            for row in self.core.universe.facets.values()
            if row.identity_ref == profile.identity_ref
        ]
        self.assertEqual({row.context_ref for row in facets}, {"ctx:one", "ctx:two"})

    def test_two_equally_supported_names_remain_ambiguous(self) -> None:
        first = self.resolver.commit(
            self.resolver.propose(mention("a1", "Alex", "ctx:one", "story", 1))
        )
        # Force a second Alex by selecting the always-present new-identity branch.
        proposal = self.resolver.propose(
            mention("a2", "Alex", "ctx:two", "other-story", 20)
        )
        new_candidate = next(row for row in proposal.candidates if row.creates_new_identity)
        second = self.resolver.commit(proposal, candidate_ref=new_candidate.candidate_ref)
        ambiguous = self.resolver.propose(
            mention("a3", "Alex", "ctx:one", "new-story", 30)
        )

        self.assertNotEqual(first.identity_ref, second.identity_ref)
        self.assertEqual(ambiguous.status, "ambiguous")
        self.assertIsNone(ambiguous.selected_identity_ref)
        existing = [row for row in ambiguous.candidates if not row.creates_new_identity]
        self.assertEqual(len(existing), 2)
        self.assertEqual(existing[0].score, existing[1].score)

    def test_incompatible_features_block_automatic_merge(self) -> None:
        profile = self.resolver.commit(
            self.resolver.propose(mention("s1", "Sam", "ctx:one", "story", 1))
        )
        decision = self.resolver.propose(
            mention(
                "s2",
                "Sam",
                "ctx:two",
                "story",
                2,
                gender="masculine",
            )
        )
        existing = next(
            row for row in decision.candidates if row.identity_ref == profile.identity_ref
        )

        self.assertIn("feature-conflict:gender", existing.conflict_signals)
        self.assertEqual(existing.score, 0.25)
        self.assertNotEqual(decision.selected_identity_ref, profile.identity_ref)


if __name__ == "__main__":
    unittest.main()
