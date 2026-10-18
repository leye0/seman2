# Shared category-prefix trie: grammar recognition without per-rule duplication

Date: 18 October 2026. Branch: **main**. Research-only; no changes to the canonical parser or production routing.

## Why we changed direction

We originally reduced Python storage by interning repeated per-rule derivations. The unconditional versions slowed easy sentences by 27–42%, because the same rule-specific recognition work still happened and then extra indirections were added.

Next we tested a conditional `indexed` version that skipped **176,573 redundant category checks** and used compact integer partial keys on a 128-sentence sample. With cyclic GC controlled, it was **2.45% slower** on the 11 risk-routed cases and essentially equal overall. It was removed from the active parser; original source remains in commit history. Merely removing cheap checks did not remove the expensive repeated matching.

The genuinely new candidate is a **category-prefix trie of the grammar**. At the *recognition* stage, the original vector algorithm matches categories and spans; morphosyntactic traits are validated later by the lazy materializer. Therefore two rules with the same consumed RHS categories can, *at this stage*, share one prefix traversal **without being treated as the same grammatical rule**.

The static compiled trie has **521 nodes** for the **383 effective ordinary rules**. Each node retains its corresponding set of *(original rule index, dot position)* variants; suffixes, features, required evidence, scores, valence and semantic actions remain independent.

## Exact prototype semantics

`superparser/research/verbnet_lr/category_prefix_trie.py` currently REPLAYS recognized node categories and spans from a **completed canonical vector forest**. It is a non-autonomous **oracle experiment**:

- Start a trie state on one recognized category node, rather than one partial per compatible grammar rule.
- Advance that state once for each matching category/span continuation and accumulate logical child links.
- When needed, project a trie state back onto every distinct original rule/dot belonging to that prefix, without merging the rule identities.
- On nonsaturated canonical forests, compare the **set** of each rule's predecessor-group/child-node derivations against the trie group's edges.
- Do not report equivalence for forests cut short by the 20,000-item reference budget. Those can contain incomplete evidence.
- No independent lexical-lattice recognition, tree/rule materializer or standalone k-best has been implemented yet. Original grammar/lexical outputs remain the only authoritative ones.

**Critical distinction:** this replay checks projection of *logical derivation-edge sets*. It does NOT establish per-rule derivation **ordering**, binding-context equivalence, identical k-best scores, semantic graph parity or budget behavior of a hypothetical online trie. Every one of those is required before replacing the recognizer.

## Measured on real preserved Gutenberg novels

[CI audit 39176251584](https://github.com/leye0/seman2/actions/runs/39176251584);
[full 64-row artifact](https://github.com/leye0/seman2/actions/runs/39176251584/artifacts/12154427860).
Four books × four length bands (4–8, 9–16, 17–24, 25–32 tokens) × four deterministic cases per band; WordNet 3.0; 20,000 forest-item and 100,000 k-best-work caps.

| Metric | Result |
|---|---:|
| Total attempted sentences | 64 |
| Nonsaturated cases with strict state/edge projection parity | **50/50** |
| Saturated cases excluded from strict state parity | **14** |
| Original rule-specific partial states, on verified cases | **311,260** |
| Distinct trie prefix/span states on verified cases | **36,363** |
| **Theoretical prefix-state reduction from grouping** | **274,897 (88.3%)** |
| Canonical partial derivation edges matched as sets | **334,684** |
| Projection mismatches in verified cases | **0** |
| Compiled category-prefix trie nodes | 521 |

Within bands, theoretical state grouping ranged from **87.7%** for 17–24 tokens to **91.3%** for 4–8 tokens. This is **not 88% fewer live parser allocations** and **not an 88% reduction in runtime**: the replay runs *after* the canonical recognizer has already built all rule-specific forest nodes. Nor is category-only grouping permission to erase syntactic subtype/feature distinctions — every variant remains a separate downstream alternative.

Canonical recognition across all 64 took ~4.54 s and offline trie replay took ~1.17 s, but these are **not comparable** end-to-end parsers: the replay is supplied with already-recognized canonical constituents and avoids their construction. No acceleration claim is justified by those numbers.

## Required next milestones

1. Compile category-prefix trie transitions directly from the same canonical rules; retain a mapping to **every** original rule variant, its feature constraints, required evidence and semantics.
2. Build an **online category-node and shared-prefix forest**, using real lexical candidate spans as inputs, with the same treatment of punctuation, dialogue scopes, grammatical cycles and negative evidence. Do not use a canonical forest as an oracle.
3. On carefully bounded, nonsaturated cases, project **ordered** rule-specific derivations and verify full forest and top-k tree/semantic equivalence. The projection must not invent new interpretations, drop lexical subtypes or bypass grammatical constraints.
4. Define a budget-equivalence policy before testing saturated sentences: one shared trie state represents multiple original rule partials; counting it as a single state under the old 20,000 cap would artificially inflate coverage.
5. On new authors/books, compare total CPU, peak RSS, fast-path p50/p95/p99 and completion against repeated canonical A/A controls, with GC effects isolated for diagnosis and included for eventual throughput.
6. **Route only prediagnosed hard sentences** through this prototype if its hard-path benefit survives testing; easy prose and dialogue stay canonical. The ~0.034-ms predictor from previous research remains a separate, cheap decision stage.

**Decision:** grouping real grammatical recognition into a category-prefix trie is structurally plausible and projects correctly on the 50 verified oracle-based cases. It is the next major research direction, **not yet a deployed optimization or complete parser**.
