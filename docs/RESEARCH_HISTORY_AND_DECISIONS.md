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
| 18 Oct — rule-continuation predictor | Compile FIRST-category/rule-prefix compatibility from current grammar | Bitset p50 ~0.034 ms, matched-length AUC ~0.841 for saturation; predictive cost not grammatical truth | INTEGRATED as opt-in preparse router |

| 18 Oct — memory-focused online / flat prefix modes | Intern partial-edge objects after rule recognition | Some memory reductions, but first option as much as 2.4× slower; storage sharing is not computational sharing | REMOVED from main |
| 18 Oct — indexed category checks and packed keys | Skip trivial category comparisons | Even with controlled GC, routed cohort about 2.45% slower; no robust benefit | REMOVED from main |
| 18 Oct — shared category-prefix trie, lazy rule projection | Recognize grammatical prefix once, project rule-specific variants only for k-best | 42 long cases ~43% CPU saved; A/adapt/A on 128 cases ~15.6% CPU saved, with 19 saturated cases uncertified | ONLY opt-in heavy recognizer retained |
| 18 Oct — cross-book signature/subtree caching | Lookup previously seen grammar shapes and replay their constraints | Lookup ~0.18ms median but useful long subtrees rare, no recognition work saved, risk of false acceptance if traits ignored | REMOVED from main |
| 18 Oct — single-subject repository cleanup | Remove POCs, unused workflows, historical readers and induction systems | Future agents must know exactly ONE current Layer 1 architecture | main now contains the canonical and lazy-trie routes only |

## Six lessons we explicitly do NOT forget

1. **Completion is not grammatical correctness.** A forest can return complete but wrong analyses, including agreement and attachment errors; a parse produced by an internal teacher is not independent gold.
2. **Faster incomplete systems are not competitive baselines.** Compare on the same lexical lattice, held-out texts, budgets, alternatives, roles and semantic correctness.
3. **Do not lose ambiguity to gain speed.** A single POS or first template hit hides alternatives; subcategories, valence and required evidence matter.
4. **Do not conflate memory hits and understanding.** Exact cache replay, successful pattern matching and partial witness discovery do not prove generalization or complete Layer 1 syntax.
5. **Don't use punctuation as an unverified shortcut.** Dialogue quotation, punctuation, initials and cuts were genuine data-quality/segmentation failures, not necessarily rule deficits.
6. **Don’t solve one benchmark by silently weakening the contract.** Over-aggressive early filters lost old successes; speculative pre-splits raised runtime or changed top trees; post-failure recovery was safe for successes but added cost.

## Où sont les preuves originales ?

**Les exécutables historiques ne sont PLUS dans main.** Ils restent récupérables dans [archive/pre-simplification-2026-10-18](https://github.com/leye0/seman2/tree/archive/pre-simplification-2026-10-18), au commit `d161e4bc34f2c344a7360d92329f2dd985133acd`, ainsi que dans l'historique de Git et les anciennes Actions. Les anciennes notes de `research/verbnet_lr`, moteurs compiled LR, snapping et autres doivent être consultés **sur la branche archivée**.

Le SEUL code à exécuter et les commandes validées : [RUN_CURRENT_LAYER1.md](RUN_CURRENT_LAYER1.md). Architecture : [ARCHITECTURE_LAYER1.md](ARCHITECTURE_LAYER1.md). Limites actuelles : [KNOWN_LIMITS_AND_ROADMAP.md](KNOWN_LIMITS_AND_ROADMAP.md).

**Décision actuelle du propriétaire :** suspendre pour le moment les optimisations par nouveaux patterns. Améliorer la correction et la couverture grammaticale des phrases difficiles et dialogues avec les moteurs présents.
