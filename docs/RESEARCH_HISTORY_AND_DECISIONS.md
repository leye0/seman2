# How Seman2 reached the current Layer 1 architecture

**Purpose:** do not repeat our research mistakes merely because an experiment once benchmarked faster. The git history and referenced run artifacts preserve original experiments; this document records decisions and the important *negative results*. Historical success was never a guarantee of linguistic accuracy.

| Phase (2026) | What we tried | What it taught us | Current disposition |
|---|---|---|---|
| 7 Oct — external TRIPS | Rich external structured parsing | High-quality linguistic structure is possible, but ~908 ms/phrase and ~87% external parser time made this route unsuitable for our latency target | Historical reference; not Layer 1 runtime |
| 8 Oct — generic chart/packed parses | Full ambiguity with grammatical traits and provenance | Strong completeness contract but severe combinatorial tails (initial 40-case p90 ~9.8 s, worst ~37.9 s) | Structural contract retained; old chart algorithm not the canonical recognizer |
| 8–10 Oct — state/derivation dedup | Rule indexing, shared states and lazy semantic construction | Avoid needless copies without losing alternatives; microbenchmarks alone often gave misleading speedups | Shared forest and lazy materialization retained |
| 10–14 Oct — canonical vector forest | `VectorGrammar`, lazy k-best and bounded hierarchical clauses | On an earlier novel: 2,663/3,326 complete below 1 s; 614 timeouts; complete analyses retain NP/VP/PP, traits and anchors | **Canonical Layer 1** |
| 11–15 Oct — predictive versions | Trained anticipatory parsing / fallbacks | One version fell to 272/300 completion with p95 ~2.2 s; another recovered 300/300 with p95 ~86 ms but top-tree structure matching fell to ~56% vs ~75% for vector reference | **Abandoned as authority**; fast ≠ correct |
| 15–17 Oct — compiled left-to-right | One-path VerbNet/L-R reader | Same-input comparison on 150 Gutenberg samples: 10/150 complete vs 98/150 vector; L-R was faster but mostly did not complete sentences | **Rejected as primary parser** |
| 16–17 Oct — complete and partial snapping/C templates | Replay learned structures and compose chunks | High replay hits can be tautological or only partial; memorized trees, score/rule mismatches and invalid global trees prevent treating hit rate as accuracy | Keep historical evidence; not canonical |
| 17 Oct — directly consolidate grammar | Add agreement/valency/morphology constraints in actual declarative grammar + lexical pipeline | On 120 positives and 24 negatives: 120 positives complete and incorrect negative acceptances reduced 19→10; no overlay needed | **Keep corrections in grammar and segmentation** |
| 17–18 Oct — hybrid C/vector | C suggests while vector verifies | Local witnesses can exist, but reuse did not robustly improve p50; preserving global forest / exact syntax parity is mandatory | Experimental branch history, not production authority |
| 17–18 Oct — clean novels, dialogue boundaries | Four cleaned public-domain novels; preserve quotation and initials; specialized dialogue grammar | Quote corruption and sentence-boundary artifacts masqueraded as grammar failures. New audit 74/160 dialogue-scoped parses in a length-stratified sample, not 160 verified speech turns | **Keep cleaned corpus + quote-aware parser** |
| 18 Oct — inspect 5,000 slow sentences | Explain forest and k-best saturation, length vs complexity | Top 10% consume ~73% of processing time in historical run; forest often hits 20,000 states on 25–32 tokens; k-best has separate tail | Optimize selectively; do not penalize fast sentences |
| 18 Oct — lexical category product | Precompute `Σ log2(k_i)` and feature-aware products | Category AUC ~0.940, subtype AUC ~0.960 for saturation overall, but token count ~0.975; raw ambiguity mostly recapitulated sentence length | Useful cheap diagnostic, insufficient as router |
| 18 Oct — rule-continuation predictor | Compile FIRST-category/rule-prefix compatibility from existing grammar | Bitset prototype p50 ~0.034 ms, matched-length AUC ~0.841 for rule start pressure and saturation; predictor is neither a parser nor a correctness guarantee | **Current read-only research POC**, candidate for routing experiments |

## Six lessons we explicitly do NOT forget

1. **Completion is not grammatical correctness.** A forest can return complete but wrong analyses, including agreement and attachment errors; a parse produced by an internal teacher is not independent gold.
2. **Faster incomplete systems are not competitive baselines.** Compare on the same lexical lattice, held-out texts, budgets, alternatives, roles and semantic correctness.
3. **Do not lose ambiguity to gain speed.** A single POS or first template hit hides alternatives; subcategories, valence and required evidence matter.
4. **Do not conflate memory hits and understanding.** Exact cache replay, successful pattern matching and partial witness discovery do not prove generalization or complete Layer 1 syntax.
5. **Don't use punctuation as an unverified shortcut.** Dialogue quotation, punctuation, initials and cuts were genuine data-quality/segmentation failures, not necessarily rule deficits.
6. **Don’t solve one benchmark by silently weakening the contract.** Over-aggressive early filters lost old successes; speculative pre-splits raised runtime or changed top trees; post-failure recovery was safe for successes but added cost.

## Where the original evidence lives

The cleaned corpus and research notes remain versioned. Primary narrative:
- `superparser/research/verbnet_lr/PARSER_LINEAGE_AND_HYBRID_AUDIT.md`
- `.../CANONICAL_VECTOR_GUTENBERG_DECISION.md`
- `.../DIRECT_GRAMMAR_CONSOLIDATION_RESULTS.md`
- `.../DIALOGUE_GRAMMAR_STATUS.md`
- `.../HEAVY_SENTENCE_ADAPTIVE_FINDINGS.md`
- `.../PREPARSE_LEXICAL_AMBIGUITY_AUDIT.md`
- `.../STRUCTURAL_CONTINUATION_PROBE_FINDINGS.md`

Historical scripts removed during the cleanup are retrievable at the pre-cleanup commit `e8322eb7fdb6ab1213c1a44f9b3d032f29d4d7a8` or earlier history. Never replace a historical measurement with data from a different corpus, budget or parser version.
