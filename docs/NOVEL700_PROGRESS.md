# Novel-700 — first source-grounded correction pass

The immutable initial 77/100 baseline is unchanged. The current result now has **88/100 complete trees**, an increase of eleven source-grounded constructions on the original N601–N700 anchors. Twelve cases remain incomplete: N624, N625, N639, N643, N647, N648, N649, N660, N661, N669, N672, N691.

The newly recovered cases are N603, N615, N619, N623, N641, N652, N654, N665, N666, N685 and N700. Each has an independently constructed grammatical positive, a near-miss negative that is not accepted by the new construction, and assertions on selected semantic links in `test_novel_700_attachments.py`. The original negative controls may still parse through unrelated grammar where grammatically appropriate; the specific construction must not accept them.

N612 remains complete but the overt *saw* is selected as the verb *see* rather than the unrelated *saw* lemma; this intentional sense/graph change is separately recorded, not hidden as unchanged. It has an appropriate visual object (*beautiful towns*) and a shared subject with *passed*. The original 77-case complete set was not considered automatically attachment-verified; only reviewed entries receive a verification verdict.

Novel-600 replay yields 100/100 and its protected signatures remain intact. The preserved initial N700 outcomes, source spans, corpus anchors and budgets (50,000 chart items, 500,000 k-best units, 10 seconds per source case) are unchanged. Do not open Novel-800 until the remaining 12 cases and the 76 currently unreviewed complete trees have been individually examined and accepted.
