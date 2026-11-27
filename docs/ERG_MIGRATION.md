# ERG migration (2026-11-27)

Pre-migration snapshot: 99595036d49d3756d080b9e798d94640d73aae4c. All historical rules, graphs, fixtures, and experiments are recoverable from this commit; no history rewritten.

## What is retained and why

- Exact Gutenberg cleaning, paragraph boundaries, quote scanner, clipped apostrophes and emphasis, semicolon cohesion, original spans, reporting clauses, split speech, nested quotes, narratorial asides and context-dependent status. Retain source-only provisional span recognizers, including their compatibility helpers; they never constrain ACE.
- Original four cleaned novels and Novel-1000 v3 source pins, independent of the old parser. Retain curriculum/source reference data and compiled VerbNet for future semantic enrichment.
- Important lexical knowledge: historical literary lexicon documents compounds such as spy-glass and jolly-boat, and source-scoped entries document constructions such as ought selecting to and independent genitives. Keep these as inactive evidence in the Git snapshot; do not import into ERG without verified novel failures and independent contrasts.
- Marked nonstandard agreement/dialect observations are useful for dialogue diagnostics: preserve exact source, do not normalize away deviations or guess speaker intent. Native MRS argument roles are not equivalent to a VerbNet/FrameNet role. Old recipes sometimes used specific lemma allowlists; recover as research evidence, not automatic overrides.
- Original parser's old grammar, chart search, k-best, lexical lattice, semantic recipes, source-scoped proof rules, outdated CI and historical experiments are removed from active main. Source helpers remain solely for extraction annotations.

## Evidence for the switch

Historical frozen Novel-1000: old Seman2 1000 complete, ERG 957 with returned analyses; sample audit 54/75 vs 64/75 first, 67/75 any rank (manual, single adjudicator). ERG opaque content flags and failure remain separate. [Native run](https://github.com/leye0/seman2/actions/runs/45756780706).

Independent raw UD-EWT restricted projection [run 45899719828](https://github.com/leye0/seman2/actions/runs/45899719828) at 99595036d49d3756d080b9e798d94640d73aae4c: 200 deterministic eligible texts, old engine 132 completed vs ERG 191 native. 519 gold relations: old projection 123 (23.7%), ERG first 390 (75.1%), any first ten 437 (84.2%). Subject 52/93 vs 87/93; object 61/159 vs 127/159; adjective modification 0/137 vs 106/137; adverb modification 10/130 vs 70/130. These are restricted relation recall, not LAS, and asymmetric representation projection (notably zero adjective hits) may underestimate old Seman2. No claim of full semantic accuracy. Historical current-main old suite had 28 failures out of 519; many due to source anchor drift. Do not suppress new source regressions or change anchor hashes.

## New boundary

The production API is Parser.parse / parse_paragraph. It uses only ACE and preserves native outputs. Full source units and independent source components are never merged into invented syntax. Further ranking, lexical enrichment, co-reference, repair of opaque/failed analyses and external validation remain future work. Component diagnostics are opt-in in benchmark so full-source coverage is comparable.
