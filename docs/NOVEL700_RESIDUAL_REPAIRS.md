# Novel-700 — completion and selected-attachment review of the 12 residual cases

**Scope.** Twelve formerly incomplete source-anchored units in the frozen
N601–N700 cohort. This work does not alter the input text, Gutenberg selection,
source spans, WordNet 3.0, original baseline or the 50,000-item / 500,000-work /
10-second per-case budgets. All corpus inputs use `parse_corpus_case`.

The baseline remains **77/100**; the first correction pass was **88/100**.
The follow-up targets the previously unresolved **N624, N625, N639, N643,
N647, N648, N649, N660, N661, N669, N672 and N691**.

## Source-grounded constructions and intended selected relations

| Case | Construction | Source-grounded rank-one and semantic checks |
| --- | --- | --- |
| N624 | Independent semicolon parataxis followed by a depictive participle | Prove both finite clauses separately; `impelled` is a supplement of `sprang`, with overt `by all the feelings`; `which` is relative to feelings, `one being` is the quantified object of `arm`, and `the existence of another` is a nested genitive under `against` |
| N625 | Semicolon contrast with existential and object relative | Distinguish the first act `I thank you`, `all that you mention is nothing to me`, and `there is no comfort`; the relative `which I am capable of receiving` belongs to comfort, not the previous clause |
| N639 | Existential with dashed nominal repair | Keep both overt `--` marks, `no doubt` and `surely` as stance modifiers, `Jim` as a vocative, and `bad or good` as disjunctive predication over the repeated something |
| N643 | Intercalated reporter and two overt wh questions | First quote `Oh, doctor,` is vocative; `we cried` reports two questions, `what shall we do?` then `Where is he wounded?`; no invented stops or subject of `Oh` |
| N647 | Coordinated superlative and instrument cleft | Guineas is the plural subject of `were`; `with these only` is focus, and `how to make her count` has the **bare causative predicate** `make`, object `her`, verbal bare complement `count`; the old noun phrase analysis of `her count` is rejected |
| N648 | Progressive with depictive participle and temporal parataxis | `leaving the candle by the empty chest` modifies the groping event; the second time frame has `we had opened` and the coordinated state `were in full retreat` |
| N649 | Parallel indirect-manner complements | `how well he bore these slights` and `with what unwearying politeness he kept on trying` retain their respective predicates; `with all` modifies `ingratiate`, not `politeness` |
| N660 | Negative minor response, vocative and possessive gerund in modal question | `Not I!` is a minor act; `my dear Daisy` is the vocative; `my calling you Daisy` is the gerundial complement of `mind` with its own object and predicate nominal |
| N661 | Dialectal title with epistemic question tag | Preserve original `Mas’r` and `d’ye` as exact attested source spans and morphology, rather than synthesizing `Master` or `do you` in the text; `shall you see her` is modal interrogative content and `d’ye think` is its speaker-oriented epistemic tag |
| N669 | As-to nominal topic and overt reporter | `As to a fish-kittle` is a topic, **not** an adverbial subordinate; `Mrs. Crupp said` is the reporter; `well!` precedes a modal interrogative with coordinated `come and look at the range` |
| N672 | Paired statements within one original quotation | Preserve `I have almost forgotten ... but to go out tossing on the sea here.` and the elliptical wish `I wish there was not.` as separate source sentences in one quotation, not two resampled corpus units |
| N691 | Two source quotes separated by speaker tag, affected adjectival reprise, emphatic polar question | `I am grieved indeed` precedes reporter `cried Darcy`; `grieved--shocked.` is a reparative supplement, and `But is it certain--absolutely certain?` is a question with local degree emphasis |

## Proof obligations and limits

- Every recovery is checked on the original frozen source and a separately
  extracted grammatical positive, with a matched near-miss negative that
  cannot use the new construction. Tests assert the **selected** rule, full
  source span, absence of chart/k-best overrun and source-relative semantic edges.
- The detailed tests for N624 and N647 also assert nested constituent
  categories and exact lexical spans, to distinguish a plausible full root
  from a semantically misattached object.
- Replaying Novel-600 must leave **all 100 accepted tree and graph signatures
  unchanged**. Replaying Novel-700 must leave the **88 previously completed**
  analyses byte-identical, including N612's already-reviewed `saw` reading.
- Novel-500's 500 accepted selected trees, the 30 real dialogue anchors and
  the direct syntax positive/negative certificate are separately protected.
- A count of **100 completed parses does not imply 100 manually verified
  semantic trees**. The 76 existing complete trees without individual source
  review remain pending. Do not create a Novel-700 accepted pin or sample
  Novel-800 until those 76 have received their own per-tree review.

The outcome fingerprints and source-complete graph signatures are stored in
`novel-700-current.json` and the individual verdicts in
`novel-700-review.json`; the initial and frozen cohort records remain
immutable. The focused tests live in `test_novel_700_residual.py`.
