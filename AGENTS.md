# Seman2 contract

- Work directly on main; leave no open pull requests.
- ERG/ACE is the only grammatical engine. Never reintroduce custom production grammar, source-specific parse plans or semantic recipe dispatch.
- Keep the source extraction and quote/discourse graph lossless. Original semicolons, punctuation, quote marks, book offsets and source identities survive. No manufactured punctuation or silently closed quotations. Context-dependent units remain visible.
- Source constituent roles/governors are provisional. Whole-utterance native results and separately parsed speech/reporting spans are distinct; never count a component as proof of a full analysis. Preserve all returned MRS, derivations, ranks and quality flags.
- Preserve the Novel-1000 v3 manifest and exact source anchors. Fail on source drift. Coverage is not correctness; opacity and resource failures remain explicit.
- Enrichment from WordNet/VerbNet/FrameNet or historical lexical observations must be separate, provenance-bearing and validated against independent annotations; never silently rewrite source or native MRS.
- Run retained source tests and native benchmark. Historical engine and experimental data are in Git history, not active grammar.
